from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from api.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "contracts" / "openapi" / "openapi.yaml"
ROUTERS_DIR = REPO_ROOT / "backend" / "src" / "api" / "routers"

ERROR_RESPONSE_ROUTES = {
    "PasswordChangeRejected": ("auth.py", "change_password_route", 400),
    "ResetPasswordRejected": ("auth.py", "reset_password_route", 400),
    "ResetTokenGone": ("auth.py", "reset_password_route", 410),
    "AcceptInviteRejected": ("invites.py", "accept_invite_route", 400),
    "AcceptInviteTokenGone": ("invites.py", "accept_invite_route", 410),
    "InviteCreateRejected": ("invites.py", "create_invite_route", 400),
    "InviteAlreadyPending": ("invites.py", "create_invite_route", 409),
}

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


def _contract_error_codes(spec: dict[str, Any], response_name: str) -> set[str]:
    response = spec["components"]["responses"][response_name]
    schema = response["content"]["application/json"]["schema"]
    for part in schema["allOf"]:
        part = _resolve_ref(spec, part)
        properties = part.get("properties", {})
        if "error" not in properties:
            continue
        error_schema = _resolve_ref(spec, properties["error"])
        code_schema = error_schema.get("properties", {}).get("code", {})
        if "enum" in code_schema:
            return set(code_schema["enum"])
    raise AssertionError(f"{response_name} has no error.code enum")


def _route_error_codes_by_status(
    router_file: str, function_name: str
) -> dict[int, set[str]]:
    tree = ast.parse((ROUTERS_DIR / router_file).read_text())
    codes_by_status: dict[int, set[str]] = {}
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    for node in ast.walk(function):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "ApiError":
            continue
        status = node.args[0].value
        code = next(kw.value.value for kw in node.keywords if kw.arg == "code")
        codes_by_status.setdefault(status, set()).add(code)
    return codes_by_status


@pytest.mark.parametrize("response_name", list(ERROR_RESPONSE_ROUTES))
def test_error_code_fidelity(response_name: str):
    contract = _load_contract()
    contract_codes = _contract_error_codes(contract, response_name)
    router_file, function_name, status = ERROR_RESPONSE_ROUTES[response_name]
    route_codes = _route_error_codes_by_status(router_file, function_name).get(
        status, set()
    )
    assert route_codes == contract_codes
