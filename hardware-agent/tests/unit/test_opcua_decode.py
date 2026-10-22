import subprocess
import sys


def test_pinned_decoder_rejects_lengths_arrays_and_dimensions_before_expansion() -> (
    None
):
    code = """
from asyncua import ua
from asyncua.ua import ua_binary as b
from asyncua.common.utils import Buffer
from agent.ot.opcua.bounded_decode import install
cached = b._create_uatype_array_deserializer(ua.VariantType.Int32)
cached_recursive = b._create_dataclass_deserializer(ua.Argument)
called = False
original_unpack = b.Primitives1.Int32.unpack_array
def spy(data, size):
    global called
    if size > 1024:
        called = True
        raise AssertionError('oversized array reached element unpack')
    return original_unpack(data, size)
b.Primitives1.Int32.unpack_array = spy
install()
def rejects(call):
    try: call()
    except ua.UaError: return
    raise AssertionError('decoder accepted an oversized value')
guarded = b._create_uatype_array_deserializer(ua.VariantType.Int32)
assert cached is not guarded
assert cached_recursive is not b._create_dataclass_deserializer(ua.Argument)
rejects(lambda: b._Bytes.unpack(Buffer(b'\\x01\\x00\\x01\\x00' + b'x')))
rejects(lambda: b._String.unpack(Buffer(b'\\x01\\x04\\x00\\x00' + b'x')))
rejects(lambda: guarded(Buffer(b'\\x01\\x04\\x00\\x00')))
assert not called
rejects(lambda: b._create_list_deserializer(ua.Int32)(Buffer(b'\\x01\\x04\\x00\\x00')))
old_type_factory = b._create_type_deserializer
def guarded_type_factory(*args):
    return lambda data: spy(data, 0)
b._create_type_deserializer = guarded_type_factory
rejects(lambda: b._create_list_deserializer(ua.Int32)(Buffer(b'\\x01\\x04\\x00\\x00')))
assert not called
b._create_type_deserializer = old_type_factory
rejects(lambda: b._reshape([1], [2]))
rejects(lambda: b._reshape([], [1025]))
rejects(lambda: b._reshape([], [1024, 0, 100]))
assert b._reshape([1, 2, 3, 4], [2, 2]) == [[1, 2], [3, 4]]
assert b._reshape([], [2, 0]) == [[], []]
rejects(lambda: b._reshape([], [-1]))
rejects(lambda: b._reshape([], [0] * 9))
rejects(lambda: b._reshape([], [1025, 0]))
assert b._create_list_deserializer(ua.Int32)(Buffer(b'\\xff\\xff\\xff\\xff')) == []
variant = bytes([ua.VariantType.Null.value])
for _ in range(10): variant = bytes([ua.VariantType.Variant.value]) + variant
rejects(lambda: b.variant_from_binary(Buffer(variant)))
type_id = b.nodeid_to_binary(ua.NodeId(ua.ObjectIds.Argument_Encoding_DefaultBinary))
rejects(lambda: b.extensionobject_from_binary(Buffer(
    type_id + b'\\x01\\x01\\x00\\x01\\x00'
)))
rejects(lambda: b.extensionobject_from_binary(Buffer(type_id + b'\\xff')))
rejects(lambda: b.extensionobject_from_binary(Buffer(
    type_id + b'\\x01\\x05\\x00\\x00\\x00x'
)))
rejects(lambda: b.extensionobject_from_binary(Buffer(
    type_id + b'\\x01\\xfe\\xff\\xff\\xff'
)))
body = (b'\\xff\\xff\\xff\\xff' + b'\\x00' + b'\\xff\\xff\\xff\\xff'
        + b'\\x01\\x04\\x00\\x00' + b'\\x00')
body_length = b.Primitives.Int32.pack(len(body))
rejects(lambda: b.extensionobject_from_binary(Buffer(
    type_id + b'\\x01' + body_length + body
)))
null_array_with_dimensions = (
    bytes([ua.VariantType.Int32.value | 0xC0])
    + b'\\xff\\xff\\xff\\xff'
    + b'\\x03\\x00\\x00\\x00'
    + b'\\x00\\x04\\x00\\x00'
    + b'\\x00\\x00\\x00\\x00'
    + b'\\x64\\x00\\x00\\x00'
)
b.Primitives1.Int32.unpack_array = original_unpack
rejects(lambda: b.variant_from_binary(Buffer(null_array_with_dimensions)))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_importing_worker_dependencies_does_not_patch_parent_decoder() -> None:
    code = """
from asyncua.ua import ua_binary as b
original = b._Bytes.unpack
import agent.ot.opcua.worker
assert b._Bytes.unpack is original
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_pinned_decoder_preserves_generic_lists_and_variant_arrays() -> None:
    code = """
from asyncua import ua
from asyncua.ua import ua_binary as b
from asyncua.common.utils import Buffer
from agent.ot.opcua.bounded_decode import install
install()
generic = b._create_list_deserializer(ua.Int32)(Buffer(
    b'\\x02\\x00\\x00\\x00\\x01\\x00\\x00\\x00\\x02\\x00\\x00\\x00'
))
assert generic == [1, 2]
array = bytes([ua.VariantType.Int32.value | 0x80]) + (
    b'\\x02\\x00\\x00\\x00\\x02\\x00\\x00\\x00\\x03\\x00\\x00\\x00'
)
decoded = b.variant_from_binary(Buffer(array))
assert decoded.Value == [2, 3]
assert decoded.Dimensions is None
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_pinned_decoder_round_trips_multidimensional_variant_arrays() -> None:
    code = """
from asyncua import ua
from asyncua.ua import ua_binary as b
from asyncua.common.utils import Buffer
from agent.ot.opcua.bounded_decode import install
install()
values = [
    ua.Variant([[1, 2], [3, 4]], ua.VariantType.Int32, Dimensions=[2, 2]),
    ua.Variant([[[1, 2], [3, 4]], [[5, 6], [7, 8]]], ua.VariantType.Int32,
               Dimensions=[2, 2, 2]),
]
for value in values:
    wire = b.variant_to_binary(value)
    decoded = b.variant_from_binary(Buffer(wire))
    assert decoded.Dimensions == value.Dimensions
    assert decoded.Value == value.Value
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
