from __future__ import annotations

import contextvars
import functools
import importlib.metadata
from typing import Any, Callable

from asyncua import ua
from asyncua.ua import ua_binary as binary

MAX_ARRAY = 1024
MAX_DEPTH = 8
MAX_STRING_BYTES = 1024
MAX_BODY_BYTES = 65536
_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "opcua_decode_depth", default=0
)
_installed = False


def _enter(call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    depth = _depth.get()
    if depth >= MAX_DEPTH:
        raise ua.UaError("decode_limit")
    token = _depth.set(depth + 1)
    try:
        return call(*args, **kwargs)
    finally:
        _depth.reset(token)


def _length(data: Any, cap: int, nullable: bool) -> int:
    size = binary.Primitives.Int32.unpack(data)
    if size == -1 and nullable:
        return size
    if size < 0 or size > cap:
        raise ua.UaError("decode_limit")
    if hasattr(data, "__len__") and size > len(data):
        raise ua.UaError("decode_limit")
    return size


def install() -> None:
    global _installed
    if _installed:
        return
    if importlib.metadata.version("asyncua") != "2.1.0":
        raise RuntimeError("unsupported_asyncua_version")

    original_type = binary._create_type_deserializer
    original_data = binary._create_dataclass_deserializer
    original_value = binary._create_uatype_deserializer
    original_variant = binary.variant_from_binary

    def unpack_bytes(data: Any) -> bytes | None:
        size = _length(data, MAX_BODY_BYTES, True)
        if size == -1:
            return None
        result = data.read(size)
        if len(result) != size:
            raise ua.UaError("decode_limit")
        return result

    def unpack_string(data: Any) -> str | None:
        size = _length(data, MAX_STRING_BYTES, True)
        if size == -1:
            return None
        raw = data.read(size)
        if len(raw) != size:
            raise ua.UaError("decode_limit")
        return raw.decode(binary.get_string_encoding(), errors="surrogateescape")

    def array_factory(vtype: Any) -> Callable[..., Any]:
        primitive = getattr(binary.Primitives1, vtype.name, None)
        if primitive is None:
            element = binary._create_uatype_deserializer(vtype)

            def unpack(data: Any, size: int) -> Any:
                return (element(data) for _ in range(size))

        else:
            unpack = primitive.unpack_array

        def decode(data: Any) -> Any:
            size = _length(data, MAX_ARRAY, True)
            if size == -1:
                return None
            if primitive is not None and size * primitive.size > len(data):
                raise ua.UaError("decode_limit")
            return _enter(lambda: list(unpack(data, size)))

        return decode

    def list_factory(uatype: Any) -> Callable[..., Any]:
        element: Callable[..., Any] | None = None

        def decode(data: Any) -> Any:
            nonlocal element
            size = _length(data, MAX_ARRAY, True)
            if size == -1:
                return []
            if element is None:
                element = binary._create_type_deserializer(uatype, type(None))
            return _enter(lambda: [element(data) for _ in range(size)])

        return decode

    def type_factory(uatype: Any, dataclazz: type) -> Callable[..., Any]:
        return original_type(uatype, dataclazz)

    def value_factory(vtype: Any) -> Callable[..., Any]:
        return original_value(vtype)

    def data_factory(objtype: Any) -> Callable[..., Any]:
        unpack = original_data(objtype)
        return functools.wraps(unpack)(lambda data: _enter(unpack, data))

    def variant(data: Any) -> Any:
        decoded = _enter(original_variant, data)
        dimensions = decoded.Dimensions
        if dimensions is not None:
            # variant_from_binary already calls _reshape for non-null arrays.
            # Only validate dimensions here when that call is skipped for null.
            if decoded.Value is None:
                _validate_dimensions(dimensions, None)
        return decoded

    def _validate_dimensions(dimensions: list[int], actual_count: int | None) -> int:
        if not dimensions or len(dimensions) > MAX_DEPTH:
            raise ua.UaError("decode_limit")
        count = 1
        shape_work = 1
        for size in dimensions:
            if size < 0:
                raise ua.UaError("decode_limit")
            count *= size
            shape_work *= max(size, 1)
            if count > MAX_ARRAY or shape_work > MAX_ARRAY:
                raise ua.UaError("decode_limit")
        if actual_count is not None and count != actual_count:
            raise ua.UaError("decode_limit")
        return count

    def reshape(flat: list[Any], dimensions: list[int]) -> Any:
        _validate_dimensions(dimensions, len(flat))

        def nest(values: list[Any], dims: list[int]) -> Any:
            if len(dims) == 1:
                return values
            stride = 1
            for size in dims[1:]:
                stride *= size
            return [
                nest(values[index * stride : (index + 1) * stride], dims[1:])
                for index in range(dims[0])
            ]

        return nest(flat, dimensions)

    def extension(data: Any) -> Any:
        typeid = binary.nodeid_from_binary(data)
        encoding = ord(data.read(1))
        if encoding not in (0, 1, 2):
            raise ua.UaError("decode_limit")
        body = None
        if encoding in (1, 2):
            size = _length(data, MAX_BODY_BYTES, False)
            if size > len(data):
                raise ua.UaError("decode_limit")
            body = data.copy(size)
            data.skip(size)
        if typeid.Identifier == 0:
            return ua.ExtensionObject()
        cls = ua.extension_objects_by_typeid.get(typeid)
        if cls is None or encoding == 2:
            return ua.ExtensionObject(
                TypeId=typeid, Body=body.read(len(body)) if body else None
            )
        if body is None:
            raise ua.UaError("decode_limit")
        return _enter(binary.from_binary, cls, body)

    for factory in (
        "_create_uatype_deserializer",
        "_create_uatype_array_deserializer",
        "_create_list_deserializer",
        "_create_type_deserializer",
        "_create_dataclass_deserializer",
    ):
        getattr(binary, factory).cache_clear()
    binary._Bytes.unpack = staticmethod(unpack_bytes)
    binary._String.unpack = staticmethod(unpack_string)
    binary._create_uatype_array_deserializer = functools.cache(array_factory)
    binary._create_list_deserializer = functools.cache(list_factory)
    binary._create_type_deserializer = functools.cache(type_factory)
    binary._create_dataclass_deserializer = functools.cache(data_factory)
    binary._create_uatype_deserializer = functools.cache(value_factory)
    binary.variant_from_binary = variant
    binary.extensionobject_from_binary = extension
    binary._reshape = reshape
    _installed = True
