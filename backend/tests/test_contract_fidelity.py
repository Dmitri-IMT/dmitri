from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from api.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi" / "openapi.yaml"

SCHEMA_NAMES = (
    "ScanSummary",
    "ScanListResponse",
    "CommandSummary",
    "CommandDetail",
    "HostSummary",
    "ScanHostView",
    "HostDetailResponse",
    "HostListResponse",
    "ScanDetailResponse",
    "FindingListResponse",
)
OPERATION_PATHS = ("/api/v1/scans", "/api/v1/findings")


def _load_contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT_PATH.read_text())


def _resolve_ref(spec: dict[str, Any], node: Any) -> Any:
    if isinstance(node, dict) and "$ref" in node:
        target: Any = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            target = target[part]
        return _resolve_ref(spec, target)
    return node


def _normalize_minimum(value: Any) -> int | float:
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def _property_shape(spec: dict[str, Any], prop: dict[str, Any]) -> dict[str, Any]:
    prop = _resolve_ref(spec, prop)
    shape: dict[str, Any] = {}
    if "enum" in prop:
        shape["enum"] = sorted(prop["enum"])
    if "format" in prop:
        shape["format"] = prop["format"]
    if "minimum" in prop:
        shape["minimum"] = _normalize_minimum(prop["minimum"])
    if "anyOf" in prop:
        parts = [_resolve_ref(spec, part) for part in prop["anyOf"]]
        shape["nullable"] = any(part.get("type") == "null" for part in parts)
        non_null = [
            part
            for part in prop["anyOf"]
            if _resolve_ref(spec, part).get("type") != "null"
        ]
        if len(non_null) == 1:
            shape.update(_property_shape(spec, non_null[0]))
        return shape
    if "type" in prop:
        shape["type"] = prop["type"]
    if "items" in prop:
        items = _resolve_ref(spec, prop["items"])
        if "properties" in items:
            shape["items"] = _schema_fingerprint(spec, prop["items"])
        else:
            shape["items"] = _property_shape(spec, prop["items"])
    return shape


def _schema_fingerprint(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    schema = _resolve_ref(spec, schema)
    properties = schema.get("properties", {})
    return {
        "additionalProperties": schema.get("additionalProperties"),
        "required": sorted(schema.get("required", [])),
        "properties": {
            name: _property_shape(spec, prop) for name, prop in properties.items()
        },
    }


def _parameter_schema_shape(
    spec: dict[str, Any], param: dict[str, Any]
) -> dict[str, Any]:
    param = _resolve_ref(spec, param)
    schema = _resolve_ref(spec, param["schema"])
    shape = _property_shape(spec, schema)
    if "default" in schema:
        shape["default"] = schema["default"]
    if "maximum" in schema:
        shape["maximum"] = _normalize_minimum(schema["maximum"])
    return shape


def _parameter_entry(spec: dict[str, Any], param: dict[str, Any]) -> dict[str, Any]:
    param = _resolve_ref(spec, param)
    schema = _parameter_schema_shape(spec, param)
    if not param.get("required", False):
        schema["nullable"] = True
    return {
        "in": param["in"],
        "required": param.get("required", False),
        "schema": schema,
    }


def _operation_parameters(spec: dict[str, Any], path: str) -> dict[str, dict[str, Any]]:
    raw = spec["paths"][path]["get"]["parameters"]
    result: dict[str, dict[str, Any]] = {}
    for param in raw:
        resolved = _resolve_ref(spec, param)
        result[resolved["name"]] = _parameter_entry(spec, param)
    return result


def _app_schema(name: str) -> dict[str, Any]:
    return app.openapi()["components"]["schemas"][name]


def _app_operation_parameters(path: str) -> dict[str, dict[str, Any]]:
    spec = app.openapi()
    raw = spec["paths"][path]["get"]["parameters"]
    return {param["name"]: _parameter_entry(spec, param) for param in raw}


def test_response_status_codes_not_compared_open_item_1():
    contract = _load_contract()
    app_spec = app.openapi()
    for path in OPERATION_PATHS:
        contract_codes = set(contract["paths"][path]["get"]["responses"])
        app_codes = set(app_spec["paths"][path]["get"]["responses"])
        assert "400" in contract_codes
        assert "422" in app_codes
        assert contract_codes != app_codes


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_schema_matches_contract(schema_name: str):
    contract = _load_contract()
    contract_schema = contract["components"]["schemas"][schema_name]
    assert _schema_fingerprint(contract, contract_schema) == _schema_fingerprint(
        app.openapi(), _app_schema(schema_name)
    )


@pytest.mark.parametrize("path", OPERATION_PATHS)
def test_query_parameters_match_contract(path: str):
    contract = _load_contract()
    contract_params = _operation_parameters(contract, path)
    app_params = _app_operation_parameters(path)
    assert set(contract_params) == set(app_params)
    for name in contract_params:
        assert contract_params[name] == app_params[name]
