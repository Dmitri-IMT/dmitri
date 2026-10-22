from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import yaml
from api.core import home_constants
from api.main import app
from api.schemas.agent_frames import AgentUpdateFrame

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
    "ScanRunningConflict": ("scans.py", "delete_scan_route", 409),
}

SCHEMA_NAMES = (
    "AssessmentEvidencePayload",
    "FindingEvidenceObservationPayload",
    "FindingEvidenceMethodCounts",
    "FindingEvidenceConfidenceCounts",
    "FindingEvidenceSummary",
    "DeviceProfilePayload",
    "ExposurePayload",
    "ExposureRead",
    "ScanSummary",
    "ScanListResponse",
    "CommandSummary",
    "CommandDetail",
    "NspiOptions",
    "HostSummary",
    "ScanHostView",
    "IndustrialServiceView",
    "HostScanHistoryEntry",
    "HostDetailResponse",
    "HostListResponse",
    "ScanDetailResponse",
    "FindingListResponse",
    "ScanIngestRequest",
    "ScanIngestAcceptedResponse",
    "HostPayload",
    "OperatingSystemDetection",
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
    "AgentProtocolSupport",
    "AgentUpdateRequest",
    "AgentUpdateClaimRequest",
    "AgentUpdateClaimReceipt",
    "AgentUpdateEvidence",
    "AgentUpdateEventRequest",
    "AgentUpdateEventAck",
    "UpdateProtocolErrorDetail",
    "UpdateProtocolErrorResponse",
    "AgentUpdateAvailability",
    "AgentUpdateHistoryPage",
    "ReleaseSummary",
    "UpdateOperationView",
    "AgentListResponse",
    "UpdateAgentTargetSubnetRequest",
    "HomeEvent",
    "HomeActivityItem",
    "HomeNotice",
    "HomeAttentionPage",
    "HomeEventsPage",
    "HomeActivityPage",
    "HomeSnapshot",
    "AIRecommendedAction",
    "AIFindingExplanation",
    "ScanAIAnalysis",
    "ScanAIAnalysisUnavailable",
    "ScanAIAnalysisNotRequested",
    "ScanAIAnalysisQueued",
    "ScanAIAnalysisFailed",
    "ScanAIAnalysisCompleted",
    "ScanReportResponse",
    "ExplainedReportSections",
    "TechnicalReportSections",
    "ReportDevice",
    "ReportService",
    "ReportIssueGroup",
    "ReportObservation",
    "ReportAdvisoryNote",
    "ReportFinding",
    "ReportAction",
    "ReportSource",
    "AIChatResponse",
    "ScanDeletionResponse",
    "HostDeletionResponse",
)
OPERATION_PATHS = ("/api/v1/scans", "/api/v1/findings", "/api/v1/hosts")

# Parameters the contract declares that v1 deliberately does not implement.
# Search is cut from v1 (docs/ui/IDEAS.md -> Hosts); see DMI-100.
UNIMPLEMENTED_PARAMS = {("/api/v1/hosts", "q")}


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
    if "exclusiveMinimum" in prop:
        shape["exclusiveMinimum"] = _normalize_minimum(prop["exclusiveMinimum"])
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


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_schema_matches_contract(schema_name: str):
    contract = _load_contract()
    contract_schema = contract["components"]["schemas"][schema_name]
    assert _schema_fingerprint(contract, contract_schema) == _schema_fingerprint(
        app.openapi(), _app_schema(schema_name)
    )


def test_agent_protocol_probe_route_matches_contract():
    contract_operation = _load_contract()["paths"][
        "/api/v1/agents/{agent_id}/update-protocol"
    ]["get"]
    app_operation = app.openapi()["paths"]["/api/v1/agents/{agent_id}/update-protocol"][
        "get"
    ]

    assert app_operation["operationId"] == contract_operation["operationId"]
    assert (
        app_operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == contract_operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
    )
    assert contract_operation["security"] == [{"AgentSignatureAuth": []}]


@pytest.mark.parametrize(
    ("path", "operation_id", "request_schema", "response_schema"),
    [
        (
            "/api/v1/agent-updates/{update_id}/claim",
            "claimAgentUpdate",
            "AgentUpdateClaimRequest",
            "AgentUpdateClaimReceipt",
        ),
        (
            "/api/v1/agent-updates/{update_id}/events",
            "reportAgentUpdateEvent",
            "AgentUpdateEventRequest",
            "AgentUpdateEventAck",
        ),
    ],
)
def test_signed_update_report_routes_match_contract(
    path: str, operation_id: str, request_schema: str, response_schema: str
) -> None:
    contract_operation = _load_contract()["paths"][path]["post"]
    app_operation = app.openapi()["paths"][path]["post"]
    assert (
        app_operation["operationId"]
        == contract_operation["operationId"]
        == operation_id
    )
    assert contract_operation["security"] == [{"AgentSignatureAuth": []}]
    assert (
        contract_operation["requestBody"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == f"#/components/schemas/{request_schema}"
    )
    assert (
        app_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == f"#/components/schemas/{request_schema}"
    )
    assert (
        contract_operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == f"#/components/schemas/{response_schema}"
    )
    assert (
        app_operation["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == f"#/components/schemas/{response_schema}"
    )
    for status in ("409", "410"):
        expected_error = "#/components/schemas/UpdateProtocolErrorResponse"
        assert (
            contract_operation["responses"][status]["content"]["application/json"][
                "schema"
            ]["$ref"]
            == expected_error
        )
        assert (
            app_operation["responses"][status]["content"]["application/json"]["schema"][
                "$ref"
            ]
            == expected_error
        )


def _enum_values(spec: dict[str, Any], node: dict[str, Any]) -> list[str]:
    node = _resolve_ref(spec, node)
    if "enum" in node:
        return sorted(value for value in node["enum"] if value is not None)
    values = []
    for part in node.get("anyOf", []):
        values.extend(_enum_values(spec, part))
    return sorted(values)


@pytest.mark.parametrize(
    ("enum_name", "model_name", "field"),
    [
        ("AssessmentConfidence", "DeviceProfilePayload", "confidence"),
        ("EvidenceKind", "AssessmentEvidencePayload", "kind"),
        ("ExposureRole", "ExposurePayload", "role"),
        ("ExposureAttention", "ExposurePayload", "attention"),
        ("ExposureConfidence", "ExposurePayload", "confidence"),
        ("MachineType", "HostPayload", "machine_type"),
    ],
)
def test_assessment_enum_matches_contract(
    enum_name: str, model_name: str, field: str
) -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    expected = sorted(contract["components"]["schemas"][enum_name]["enum"])
    app_field = app_spec["components"]["schemas"][model_name]["properties"][field]
    assert _enum_values(app_spec, app_field) == expected


@pytest.mark.parametrize(
    ("schema_name", "field", "limits"),
    [
        ("AssessmentEvidencePayload", "source", {"minLength": 1, "maxLength": 80}),
        ("AssessmentEvidencePayload", "value", {"minLength": 1, "maxLength": 160}),
        ("DeviceProfilePayload", "evidence", {"maxItems": 12}),
        ("DeviceProfilePayload", "conflicts", {"maxItems": 5}),
        ("DeviceProfilePayload", "limitations", {"maxItems": 5}),
        ("ExposurePayload", "port", {"minimum": 1, "maximum": 65535}),
        ("ExposurePayload", "observed_service", {"minLength": 1, "maxLength": 160}),
        ("ExposurePayload", "reason", {"minLength": 1, "maxLength": 240}),
        ("ExposurePayload", "evidence", {"maxItems": 12}),
    ],
)
def test_assessment_field_limits_match_contract(
    schema_name: str, field: str, limits: dict[str, int]
) -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    for key, expected in limits.items():
        contract_field = _resolve_ref(
            contract,
            contract["components"]["schemas"][schema_name]["properties"][field],
        )
        app_field = _resolve_ref(
            app_spec,
            app_spec["components"]["schemas"][schema_name]["properties"][field],
        )
        assert contract_field[key] == app_field[key] == expected


def test_finding_evidence_contract_limits_match_openapi_and_backend() -> None:
    contract = _load_contract()
    app_spec = app.openapi()
    observation = contract["components"]["schemas"]["FindingEvidenceObservationPayload"]
    app_observation = app_spec["components"]["schemas"][
        "FindingEvidenceObservationPayload"
    ]

    assert observation["additionalProperties"] is False
    assert app_observation["additionalProperties"] is False
    assert set(observation["properties"]) == set(app_observation["properties"])
    assert set(observation["properties"]) == {
        "ip",
        "port",
        "protocol",
        "unit_id",
        "condition_key",
        "method",
        "result",
        "source",
        "source_script",
        "rule_id",
        "rule_version",
        "evidence",
        "facts",
    }

    for schema in (observation, app_observation):
        properties = schema["properties"]
        port = next(
            part
            for part in properties["port"]["anyOf"]
            if part.get("type") == "integer"
        )
        unit_id = next(
            part
            for part in properties["unit_id"]["anyOf"]
            if part.get("type") == "integer"
        )
        assert port["minimum"] == 1
        assert port["maximum"] == 65535
        assert unit_id["minimum"] == 0
        assert unit_id["maximum"] == 255
        for name, maximum in (
            ("condition_key", 256),
            ("source", 64),
            ("source_script", 64),
            ("rule_id", 128),
            ("rule_version", 64),
            ("evidence", 512),
        ):
            prop = _resolve_ref(
                contract if schema is observation else app_spec,
                properties[name],
            )
            if "anyOf" in prop:
                prop = next(
                    part for part in prop["anyOf"] if part.get("type") == "string"
                )
            assert prop["maxLength"] == maximum
        facts = properties["facts"]
        assert facts["maxProperties"] == 8
        string_fact = next(
            part
            for part in facts["additionalProperties"]["anyOf"]
            if part.get("type") == "string"
        )
        assert string_fact["maxLength"] == 160
        assert facts["propertyNames"]["maxLength"] == 64

    finding = contract["components"]["schemas"]["FindingPayload"]
    assert finding["additionalProperties"] is False
    assert finding["properties"]["issue_key"] == {
        "type": ["string", "null"],
        "minLength": 1,
        "maxLength": 256,
        "default": None,
    }
    assert finding["properties"]["evidence_observations"]["maxItems"] == 16
    ingest = contract["components"]["schemas"]["ScanIngestRequest"]
    assert ingest["additionalProperties"] is False
    assert ingest["properties"]["finding_observations"]["maxItems"] == 512


def test_finding_evidence_read_summary_is_additive_and_counts_records() -> None:
    contract = _load_contract()
    summary = contract["components"]["schemas"]["FindingEvidenceSummary"]
    methods = contract["components"]["schemas"]["FindingEvidenceMethodCounts"]
    confidence = contract["components"]["schemas"]["FindingEvidenceConfidenceCounts"]

    assert summary["additionalProperties"] is False
    assert set(summary["required"]) == {
        "scope",
        "total_records",
        "by_method",
        "by_confidence",
        "conflicting_records",
        "demonstrated_records",
    }
    assert summary["properties"]["scope"]["enum"] == [
        "scan",
        "filtered_findings",
    ]
    for name in ("total_records", "conflicting_records", "demonstrated_records"):
        field = summary["properties"][name]
        assert field["type"] == "integer"
        assert field["minimum"] == 0
    assert set(methods["properties"]) == {
        "version_correlation",
        "configuration_observation",
        "specific_check",
        "textual_reference",
        "unknown",
    }
    assert set(confidence["properties"]) == {
        "tentative",
        "probable",
        "confirmed",
        "unknown",
    }
    for schema in (methods, confidence):
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        assert all(
            item["type"] == "integer" and item["minimum"] == 0
            for item in schema["properties"].values()
        )

    for schema_name in ("ScanDetailResponse", "FindingListResponse"):
        assert (
            "evidence_summary"
            in contract["components"]["schemas"][schema_name]["properties"]
        )


@pytest.mark.parametrize(
    ("schema_name", "required_fields"),
    [
        ("ScanHostView", {"machine_type", "device_profile"}),
        (
            "ScanDetailResponse",
            {"assessment_status", "assessment_policy_version", "exposures"},
        ),
        ("HostSummary", {"device_profile"}),
        (
            "HostDetailResponse",
            {
                "device_profile",
                "assessment_status",
                "assessment_policy_version",
                "exposures",
            },
        ),
    ],
)
def test_assessment_read_fields_are_required_in_contract_and_app(
    schema_name: str, required_fields: set[str]
) -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    for spec in (contract, app_spec):
        schema = spec["components"]["schemas"][schema_name]
        assert required_fields <= set(schema["required"])


@pytest.mark.parametrize(
    ("schema_name", "nullable_fields"),
    [
        ("ScanHostView", {"machine_type", "device_profile"}),
        ("ScanDetailResponse", {"assessment_policy_version"}),
        ("HostSummary", {"device_profile"}),
        (
            "HostDetailResponse",
            {"device_profile", "assessment_policy_version"},
        ),
    ],
)
def test_assessment_read_fields_are_nullable_in_contract_and_app(
    schema_name: str, nullable_fields: set[str]
) -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    for spec in (contract, app_spec):
        schema = spec["components"]["schemas"][schema_name]
        for field in nullable_fields:
            assert _property_shape(spec, schema["properties"][field])["nullable"]


def _operating_system_schema_shape(
    spec: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    schema = _resolve_ref(spec, schema)
    properties = schema["properties"]
    return {
        "additionalProperties": schema.get("additionalProperties"),
        "required": sorted(schema.get("required", [])),
        "property_names": sorted(properties),
        "name": {
            "type": properties["name"].get("type"),
            "minLength": properties["name"].get("minLength"),
        },
        "accuracy": {
            "type": properties["accuracy"].get("type"),
            "minimum": properties["accuracy"].get("minimum"),
            "maximum": properties["accuracy"].get("maximum"),
        },
        "optional_strings": {
            field: _property_shape(spec, properties[field])
            for field in ("vendor", "family", "generation", "device_type")
        },
        "cpes": {
            "type": properties["cpes"].get("type"),
            "item_type": properties["cpes"]["items"].get("type"),
            "item_minLength": properties["cpes"]["items"].get("minLength"),
            "default": properties["cpes"].get("default"),
        },
    }


def test_operating_system_constraints_match_published_contract() -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    assert _operating_system_schema_shape(
        contract,
        contract["components"]["schemas"]["OperatingSystemDetection"],
    ) == _operating_system_schema_shape(
        app_spec,
        app_spec["components"]["schemas"]["OperatingSystemDetection"],
    )


def test_host_operating_system_is_optional_and_nullable_in_both_contracts() -> None:
    contract = _load_contract()
    app_spec = app.openapi()

    host_schemas = (
        "HostPayload",
        "ScanHostView",
        "HostSummary",
        "HostDetailResponse",
        "HostScanHistoryEntry",
    )
    for spec in (contract, app_spec):
        for schema_name in host_schemas:
            host_schema = spec["components"]["schemas"][schema_name]
            assert "operating_system" not in host_schema["required"]
            assert _property_shape(
                spec, host_schema["properties"]["operating_system"]
            ) == {"nullable": True, "type": "object"}


def test_ingest_scan_endpoint_exists():
    contract = _load_contract()
    contract_operation_id = contract["paths"]["/api/v1/scans"]["post"]["operationId"]
    app_operation = app.openapi()["paths"]["/api/v1/scans"]["post"]
    assert app_operation["operationId"] == contract_operation_id == "ingestScan"


def test_scan_ai_analysis_operation_is_published():
    contract = _load_contract()
    path = "/api/v1/scans/{scan_id}/analysis"
    get_operation = contract["paths"][path]["get"]
    post_operation = contract["paths"][path]["post"]

    assert get_operation["operationId"] == "getScanAIAnalysis"
    assert get_operation["security"] == [{"FrontendBearerAuth": []}]
    assert set(get_operation["responses"]) == {"200", "401", "403", "404", "500"}
    assert post_operation["operationId"] == "requestScanAIAnalysis"
    assert post_operation["security"] == [{"FrontendBearerAuth": []}]
    assert set(post_operation["responses"]) == {
        "202",
        "401",
        "403",
        "404",
        "409",
        "500",
    }
    app_operations = app.openapi()["paths"][path]
    union = contract["components"]["schemas"]["ScanAIAnalysisResponse"]
    for method, status in (("get", "200"), ("post", "202")):
        contract_schema = contract["paths"][path][method]["responses"][status][
            "content"
        ]["application/json"]["schema"]
        app_schema = app_operations[method]["responses"][status]["content"][
            "application/json"
        ]["schema"]
        assert _resolve_ref(contract, contract_schema) == union
        assert app_schema["oneOf"] == union["oneOf"]
        assert app_schema["discriminator"] == union["discriminator"]


@pytest.mark.parametrize("path", OPERATION_PATHS)
def test_query_parameters_match_contract(path: str):
    contract = _load_contract()
    contract_params = {
        name: entry
        for name, entry in _operation_parameters(contract, path).items()
        if (path, name) not in UNIMPLEMENTED_PARAMS
    }
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
        (
            "/api/v1/agents/{agent_id}/revoke",
            "post",
            "revokeAgent",
            {"200", "401", "403", "404", "500"},
        ),
        (
            "/api/v1/agents/{agent_id}/restore",
            "post",
            "restoreAgent",
            {"200", "401", "403", "404", "500"},
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

    def collect(node: Any) -> set[str]:
        node = _resolve_ref(spec, node)
        if not isinstance(node, dict):
            return set()
        codes: set[str] = set()
        code = node.get("properties", {}).get("code", {})
        if "const" in code:
            codes.add(code["const"])
        codes.update(code.get("enum", []))
        for key in ("oneOf", "anyOf", "allOf"):
            for part in node.get(key, []):
                codes.update(collect(part))
        for prop in node.get("properties", {}).values():
            codes.update(collect(prop))
        return codes

    codes = collect(schema)
    if codes:
        return codes
    raise AssertionError(f"{response_name} has no error.code values")


def test_agent_update_error_contracts_have_closed_code_sets() -> None:
    contract = _load_contract()
    assert _contract_error_codes(contract, "AgentUpdateUnauthorized") == {
        "unauthorized"
    }
    assert _contract_error_codes(contract, "AgentUpdateConflict") == {
        "device_busy",
        "version_conflict",
        "release_not_allowed",
        "idempotency_conflict",
    }
    assert _contract_error_codes(contract, "AgentUpdateUnavailable") == {
        "device_offline",
        "bootstrap_required",
        "release_check_unavailable",
    }


def test_agent_update_frame_matches_backend_schema() -> None:
    contract_schema = _load_contract()["components"]["schemas"]["AgentUpdateFrame"]
    backend_schema = AgentUpdateFrame.model_json_schema()
    assert contract_schema["required"] == backend_schema["required"]
    assert contract_schema["additionalProperties"] is False
    assert contract_schema["properties"]["type"]["const"] == "agent_update"
    assert (
        contract_schema["properties"]["sha256"]["pattern"]
        == backend_schema["properties"]["sha256"]["pattern"]
    )


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


def test_modbus_validation_payload_absent_from_contract() -> None:
    contract = _load_contract()
    assert "ModbusValidationPayload" not in contract["components"]["schemas"]
    unit_schema = contract["components"]["schemas"]["ModbusUnitPayload"]
    assert "validations" not in unit_schema["properties"]


def test_modbus_address_range_payload_has_no_process_fields() -> None:
    contract = _load_contract()
    app_spec = app.openapi()
    for spec in (contract, app_spec):
        properties = spec["components"]["schemas"]["ModbusAddressRangePayload"][
            "properties"
        ]
        for field in (
            "values",
            "nonzero_count",
            "value_min",
            "value_max",
            "value_sha256",
        ):
            assert field not in properties
        assert "value_digest" in properties


def test_home_page_sizes_match_frontend_exports():
    source = (REPO_ROOT / "frontend" / "src" / "api" / "home.ts").read_text()
    for name in (
        "HOME_ATTENTION_PER_PAGE",
        "HOME_EVENTS_PER_PAGE",
        "HOME_ACTIVITY_PER_PAGE",
    ):
        assert f"export const {name} = {getattr(home_constants, name)}" in source


def test_agent_websocket_close_code_table_publishes_revoked():
    contract = _load_contract()
    operation = contract["paths"]["/api/v1/agents/{agent_id}/commands"]["get"]
    assert operation["operationId"] == "connectAgentCommandsWebSocket"
    rows = [
        line
        for line in operation["description"].splitlines()
        if line.strip().startswith("| `4001`")
    ]
    assert len(rows) == 1
    assert "`revoked`" in rows[0]
    assert "Park; retry once per hour" in rows[0]
    assert "admin restore" in rows[0]
