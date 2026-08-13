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
    "RoleChangeConflict": ("users.py", "update_user_role_route", 409),
    "LastAdminConflict": ("users.py", "delete_current_user_route", 409),
    "SelfTargetConflict": ("users.py", "delete_user_route", 409),
    "AgentOfflineConflict": ("agents.py", "update_agent_target_subnet_route", 409),
    "TargetSubnetNotReported": ("agents.py", "update_agent_target_subnet_route", 422),
    "ScanSubnetNotReported": ("agents.py", "create_agent_command", 422),
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
    "ScanIngestRequest",
    "ScanIngestAcceptedResponse",
    "HostPayload",
    "PortPayload",
    "FindingPayload",
    "InviteLookupRequest",
    "InviteLookupResponse",
    "OrgMember",
    "OrgMemberListResponse",
    "PendingInvite",
    "PendingInviteListResponse",
    "UpdateUserRoleRequest",
    "AgentSummary",
    "AgentDetail",
    "AgentListResponse",
    "UpdateAgentTargetSubnetRequest",
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

    prop_type = prop.get("type")
    nullable = isinstance(prop_type, list) and "null" in prop_type
    if nullable:
        remaining = [value for value in prop_type if value != "null"]
        prop_type = remaining[0] if len(remaining) == 1 else remaining

    if "enum" in prop:
        values = prop["enum"]
        nullable = nullable or None in values
        shape["enum"] = sorted(value for value in values if value is not None)
    elif "const" in prop:
        shape["enum"] = [prop["const"]]
    if "format" in prop:
        shape["format"] = prop["format"]
    if "minimum" in prop:
        shape["minimum"] = _normalize_minimum(prop["minimum"])
    if nullable:
        shape["nullable"] = True
    if prop_type is not None:
        shape["type"] = prop_type
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


def test_property_shape_type_list_and_anyof_nullable_are_equal():
    spec: dict[str, Any] = {}
    type_list = {"type": ["string", "null"]}
    any_of = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert _property_shape(spec, type_list) == _property_shape(spec, any_of)


def test_property_shape_const_and_single_enum_are_equal():
    spec: dict[str, Any] = {}
    const = {"const": "accepted"}
    enum = {"enum": ["accepted"]}
    assert _property_shape(spec, const) == _property_shape(spec, enum)


def test_property_shape_nullable_mismatch_is_different():
    spec: dict[str, Any] = {}
    nullable = {"type": ["string", "null"]}
    non_nullable = {"type": "string"}
    assert _property_shape(spec, nullable) != _property_shape(spec, non_nullable)


def test_property_shape_const_vs_wider_enum_is_different():
    spec: dict[str, Any] = {}
    const = {"const": "accepted"}
    enum = {"enum": ["accepted", "pending"]}
    assert _property_shape(spec, const) != _property_shape(spec, enum)


def test_property_shape_changed_type_is_different():
    spec: dict[str, Any] = {}
    assert _property_shape(spec, {"type": "string"}) != _property_shape(
        spec, {"type": "integer"}
    )


def test_property_shape_changed_minimum_is_different():
    spec: dict[str, Any] = {}
    assert _property_shape(
        spec, {"type": "integer", "minimum": 0}
    ) != _property_shape(spec, {"type": "integer", "minimum": 1})


def test_schema_fingerprint_removed_required_is_different():
    spec: dict[str, Any] = {}
    base = {
        "additionalProperties": False,
        "required": ["a", "b"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    missing_required = {
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    assert _schema_fingerprint(spec, base) != _schema_fingerprint(
        spec, missing_required
    )


def test_schema_fingerprint_added_property_is_different():
    spec: dict[str, Any] = {}
    base = {
        "additionalProperties": False,
        "required": [],
        "properties": {"a": {"type": "string"}},
    }
    with_extra = {
        "additionalProperties": False,
        "required": [],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    assert _schema_fingerprint(spec, base) != _schema_fingerprint(spec, with_extra)


def test_schema_fingerprint_removed_property_is_different():
    spec: dict[str, Any] = {}
    base = {
        "additionalProperties": False,
        "required": [],
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    without_b = {
        "additionalProperties": False,
        "required": [],
        "properties": {"a": {"type": "string"}},
    }
    assert _schema_fingerprint(spec, base) != _schema_fingerprint(spec, without_b)


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


def test_ingest_scan_endpoint_exists():
    contract = _load_contract()
    contract_operation_id = contract["paths"]["/api/v1/scans"]["post"]["operationId"]
    app_operation = app.openapi()["paths"]["/api/v1/scans"]["post"]
    assert app_operation["operationId"] == contract_operation_id == "ingestScan"


@pytest.mark.parametrize("path", OPERATION_PATHS)
def test_query_parameters_match_contract(path: str):
    contract = _load_contract()
    contract_params = _operation_parameters(contract, path)
    app_params = _app_operation_parameters(path)
    assert set(contract_params) == set(app_params)
    for name in contract_params:
        assert contract_params[name] == app_params[name]


def test_invite_lookup_gone_reuses_the_accept_response_component():
    contract = _load_contract()
    lookup = contract["paths"]["/api/v1/invites/lookup"]["post"]["responses"]["410"]
    accept = contract["paths"]["/api/v1/invites/accept"]["post"]["responses"]["410"]
    shared = "#/components/responses/AcceptInviteTokenGone"
    assert lookup["$ref"] == accept["$ref"] == shared
    gone_components = [
        name
        for name in contract["components"]["responses"]
        if "InviteTokenGone" in name
    ]
    assert gone_components == ["AcceptInviteTokenGone"]


@pytest.mark.parametrize(
    ("path", "operation_id", "conflict_ref", "expected_codes"),
    [
        (
            "/api/v1/users/me",
            "deleteCurrentUser",
            "#/components/responses/LastAdminConflict",
            {"204", "401", "409"},
        ),
        (
            "/api/v1/users/{user_id}",
            "deleteUser",
            "#/components/responses/SelfTargetConflict",
            {"204", "401", "403", "404", "409"},
        ),
    ],
)
def test_delete_user_operations_are_published(
    path: str, operation_id: str, conflict_ref: str, expected_codes: set[str]
):
    contract = _load_contract()
    operation = contract["paths"][path]["delete"]
    assert operation["operationId"] == operation_id
    assert operation["security"] == [{"FrontendBearerAuth": []}]
    assert set(operation["responses"]) == expected_codes
    assert "content" not in operation["responses"]["204"]
    assert operation["responses"]["409"]["$ref"] == conflict_ref
    assert "delete" in app.openapi()["paths"][path]


@pytest.mark.parametrize(
    ("path", "method", "operation_id", "expected_codes"),
    [
        (
            "/api/v1/users",
            "get",
            "listOrgUsers",
            {"200", "401", "403"},
        ),
        (
            "/api/v1/users/{user_id}",
            "patch",
            "updateUserRole",
            {"200", "401", "403", "404", "409"},
        ),
        (
            "/api/v1/invites",
            "get",
            "listPendingInvites",
            {"200", "401", "403"},
        ),
        (
            "/api/v1/invites/{invite_id}",
            "delete",
            "revokeInvite",
            {"204", "401", "403", "404"},
        ),
        (
            "/api/v1/agents/{agent_id}",
            "patch",
            "updateAgentTargetSubnet",
            {"200", "401", "403", "404", "409", "422", "500"},
        ),
    ],
)
def test_admin_operations_are_published(
    path: str, method: str, operation_id: str, expected_codes: set[str]
) -> None:
    contract = _load_contract()
    operation = contract["paths"][path][method]

    assert operation["operationId"] == operation_id
    assert operation["security"] == [{"FrontendBearerAuth": []}]
    assert set(operation["responses"]) == expected_codes
    assert method in app.openapi()["paths"][path]


def test_list_agents_is_published_as_member_readable() -> None:
    contract = _load_contract()
    operation = contract["paths"]["/api/v1/agents"]["get"]

    assert operation["operationId"] == "listAgents"
    assert operation["security"] == [{"FrontendBearerAuth": []}]
    assert set(operation["responses"]) == {"200", "401", "500"}
    assert "get" in app.openapi()["paths"]["/api/v1/agents"]


@pytest.mark.parametrize(
    ("path", "method", "status", "response_name"),
    [
        ("/api/v1/agents/{agent_id}", "patch", "409", "AgentOfflineConflict"),
        ("/api/v1/agents/{agent_id}", "patch", "422", "TargetSubnetNotReported"),
        (
            "/api/v1/agents/{agent_id}/commands",
            "post",
            "422",
            "ScanSubnetNotReported",
        ),
    ],
)
def test_agent_error_responses_reference_their_own_component(
    path: str, method: str, status: str, response_name: str
) -> None:
    contract = _load_contract()
    response = contract["paths"][path][method]["responses"][status]
    assert response["$ref"] == f"#/components/responses/{response_name}"


def test_cors_allowed_methods_example_includes_patch_and_delete():
    contract = _load_contract()
    header = contract["components"]["headers"]["Access-Control-Allow-Methods"]
    assert header["schema"]["example"] == "GET, POST, PATCH, DELETE, OPTIONS"


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
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name == function_name
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
