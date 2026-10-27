"""
Authoritative Tool Dispatcher for InfraSight (Phase 3).
Defines tool schemas for Meta Model API, validates arguments using Pydantic,
executes allowlisted actions via the Evidence Engine, and registers all returned source IDs.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, ValidationError

from backend import evidence
from backend.policy import ActionClass, PolicyEngine


# ---------------------------------------------------------------------------
# Tool Parameter Schemas for Pydantic Validation
# ---------------------------------------------------------------------------

class LookupDeviceArgs(BaseModel):
    device_id: str = Field(..., description="The server chassis ID to inspect, e.g. 'SRV-004'")


class GetHealthMetricsArgs(BaseModel):
    device_id: str = Field(..., description="Server chassis ID, e.g. 'SRV-004'")
    bay_id: str = Field(..., description="Drive bay identifier, e.g. 'BAY-04'")


class GetRecentEventsArgs(BaseModel):
    device_id: str = Field(..., description="Server chassis ID, e.g. 'SRV-004'")
    limit: int = Field(default=10, ge=1, le=50, description="Max event logs to retrieve")


class SearchManualArgs(BaseModel):
    query: str = Field(..., description="Keywords or error code to query, e.g. 'solid amber', 'ERR-PWR-8899'")
    model_id: Optional[str] = Field(None, description="Server model identifier to restrict results, e.g. 'SYNTH-SERVER-X'")


class RunDiagnosticArgs(BaseModel):
    device_id: str = Field(..., description="Target server chassis ID, e.g. 'SRV-004'")
    bay_id: str = Field(..., description="Target component or bay, e.g. 'BAY-04'")
    test_type: str = Field(..., description="Diagnostic test type: 'smart_extended_self_test', 'surface_sector_verification', 'controller_bus_health_check'")


class CreateTicketArgs(BaseModel):
    title: str = Field(..., description="Concise summary title for the ticket")
    severity: str = Field(..., description="Ticket severity: 'P1', 'P2', 'P3', 'P4'")
    summary: str = Field(..., description="Technical justification and evidence summary")


class ProposeActionArgs(BaseModel):
    action_name: str = Field(..., description="Remediation action, e.g. 'replace_physical_drive', 'restart_service'")
    target_device: str = Field(..., description="Target server chassis ID")
    target_component: Optional[str] = Field(None, description="Target component or bay")
    justification: str = Field(..., description="Evidence justification for proposing this action")


# ---------------------------------------------------------------------------
# Meta Model API Tool Definitions (OpenAI format compatible)
# ---------------------------------------------------------------------------

INVESTIGATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_device",
            "description": "Retrieve authoritative hardware configuration and model details for a server from inventory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Server chassis ID, e.g. 'SRV-004'"}
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_health_metrics",
            "description": "Fetch SMART telemetry, read error rates, temperatures, and sector health for a specific drive bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Server chassis ID, e.g. 'SRV-004'"},
                    "bay_id": {"type": "string", "description": "Drive bay identifier, e.g. 'BAY-04'"}
                },
                "required": ["device_id", "bay_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_events",
            "description": "Retrieve recent system event logs, kernel messages, and storage controller alerts for a server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Server chassis ID, e.g. 'SRV-004'"},
                    "limit": {"type": "integer", "description": "Max logs to retrieve (1-50)", "default": 10}
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_manual",
            "description": "Search authoritative technical documentation for error codes, LED meanings, and maintenance rules.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or error code"},
                    "model_id": {"type": "string", "description": "Device model ID (e.g. 'SYNTH-SERVER-X' or 'SYNTH-SERVER-Y') to filter rules"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_diagnostic",
            "description": "Trigger an online diagnostic test (SMART extended test, surface verification, or controller bus check) on a bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Server chassis ID"},
                    "bay_id": {"type": "string", "description": "Drive bay identifier"},
                    "test_type": {"type": "string", "description": "Test type: 'smart_extended_self_test', 'surface_sector_verification', or 'controller_bus_health_check'"}
                },
                "required": ["device_id", "bay_id", "test_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_ticket",
            "description": "Create a service ticket in the IT ticketing system for tracking or human dispatch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Ticket title"},
                    "severity": {"type": "string", "description": "Severity: 'P1', 'P2', 'P3', 'P4'"},
                    "summary": {"type": "string", "description": "Technical summary and cited evidence IDs"}
                },
                "required": ["title", "severity", "summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_action",
            "description": "Propose a consequential maintenance action (e.g. drive replacement, service restart). Evaluated against security policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_name": {"type": "string", "description": "Action name: 'replace_physical_drive', 'restart_service', etc."},
                    "target_device": {"type": "string", "description": "Target server chassis ID"},
                    "target_component": {"type": "string", "description": "Target bay or component"},
                    "justification": {"type": "string", "description": "Evidence justification"}
                },
                "required": ["action_name", "target_device", "justification"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Dispatcher Implementation
# ---------------------------------------------------------------------------

class ToolDispatcher:
    def __init__(self, registered_evidence_ids: Optional[set] = None):
        self.registered_evidence_ids = registered_evidence_ids if registered_evidence_ids is not None else set()

    def register_id(self, sid: Optional[str]):
        if sid:
            self.registered_evidence_ids.add(sid)

    def dispatch(
        self,
        tool_name: str,
        raw_args: Dict[str, Any],
        incident_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Validates, policy-checks, and executes a tool call.
        Returns: (result_dict, is_error_bool)
        """
        tool = (tool_name or "").strip()
        incident_context = incident_context or {}

        # 1. Allowlist and Policy Check
        policy_decision = PolicyEngine.check(tool, raw_args, incident_context)
        if not policy_decision.allowed:
            if policy_decision.requires_approval:
                # Class B action held for approval
                return {
                    "status": "held_for_approval",
                    "action_class": policy_decision.action_class.value,
                    "action_name": policy_decision.action_name,
                    "target_device": policy_decision.target_device,
                    "target_component": policy_decision.target_component,
                    "message": policy_decision.reason,
                    "approval_required": True,
                }, False
            else:
                # Class C or disallowed tool
                return {
                    "status": "policy_denied",
                    "action_class": policy_decision.action_class.value,
                    "tool": tool,
                    "error": policy_decision.reason,
                }, True

        # 2. Argument Validation and Execution
        try:
            if tool == "lookup_device":
                args = LookupDeviceArgs(**raw_args)
                devices = evidence.load_devices()
                dev = next((d for d in devices if d.get("device_id") == args.device_id), None)
                if not dev:
                    return {"status": "error", "message": f"Device '{args.device_id}' not found in inventory."}, True
                return {"status": "success", "device": dev}, False

            elif tool == "get_health_metrics":
                args = GetHealthMetricsArgs(**raw_args)
                telemetry_records = evidence.get_telemetry(args.device_id, args.bay_id)
                metrics_list = []
                for t in telemetry_records:
                    self.register_id(t.source_id)
                    metrics_list.append({
                        "source_id": t.source_id,
                        "title": t.title,
                        "summary": t.summary,
                        "payload": t.raw_payload,
                    })
                return {"status": "success", "count": len(metrics_list), "metrics": metrics_list}, False

            elif tool == "get_recent_events":
                args = GetRecentEventsArgs(**raw_args)
                event_records = evidence.search_events(args.device_id, limit=args.limit)
                events_list = []
                for e in event_records:
                    self.register_id(e.source_id)
                    events_list.append({
                        "source_id": e.source_id,
                        "title": e.title,
                        "summary": e.summary,
                        "payload": e.raw_payload,
                    })
                return {"status": "success", "count": len(events_list), "events": events_list}, False

            elif tool == "search_manual":
                args = SearchManualArgs(**raw_args)
                # Model restriction: enforce model_id from incident context if available
                model_to_use = args.model_id or incident_context.get("model_id")
                manual_records = evidence.search_manuals(query=args.query, model_id=model_to_use)
                sections = []
                for m in manual_records:
                    self.register_id(m.source_id)
                    sections.append({
                        "source_id": m.source_id,
                        "title": m.title,
                        "summary": m.summary,
                        "model_id": m.raw_payload.get("model_id") if isinstance(m.raw_payload, dict) else None,
                        "content": m.raw_payload.get("content") if isinstance(m.raw_payload, dict) else "",
                    })
                return {"status": "success", "count": len(sections), "model_filter": model_to_use, "sections": sections}, False

            elif tool == "run_diagnostic":
                args = RunDiagnosticArgs(**raw_args)
                # Lookup diagnostics fixture
                diagnostics_cache = evidence.load_diagnostics()
                # Find matching diagnostic by device and bay
                matched_diag = None
                for d in diagnostics_cache.values():
                    if d.get("target_device") == args.device_id and d.get("target_component") == args.bay_id:
                        if args.test_type in d.get("test_type", ""):
                            matched_diag = d
                            break

                if not matched_diag:
                    # Generic simulated diagnostic completed with no error
                    diag_id = f"EV-DIAG-{args.device_id.replace('-', '')}-{args.bay_id.replace('-', '')}-AUTO"
                    matched_diag = {
                        "diagnostic_id": diag_id,
                        "target_device": args.device_id,
                        "target_component": args.bay_id,
                        "test_type": args.test_type,
                        "status": "completed",
                        "result_summary": f"Simulated {args.test_type} completed on {args.device_id} {args.bay_id}. No uncorrectable faults detected."
                    }

                diag_id = matched_diag.get("diagnostic_id")
                self.register_id(diag_id)

                is_fail = matched_diag.get("status") == "failed"
                return {"status": "completed" if not is_fail else "failed", "diagnostic": matched_diag}, is_fail

            elif tool == "create_ticket":
                args = CreateTicketArgs(**raw_args)
                ticket_id = f"TICK-{len(self.registered_evidence_ids) + 1000}"
                return {
                    "status": "created",
                    "ticket_id": ticket_id,
                    "title": args.title,
                    "severity": args.severity,
                    "summary": args.summary
                }, False

            else:
                return {"status": "error", "error": f"Unknown tool: '{tool}'"}, True

        except ValidationError as ve:
            return {"status": "invalid_arguments", "error": f"Argument schema validation failed: {str(ve)}"}, True
        except Exception as ex:
            return {"status": "execution_error", "error": str(ex)}, True
