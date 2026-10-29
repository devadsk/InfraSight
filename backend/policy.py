"""
Backend Security and Action Policy Engine (Phase 3 & 4).
Enforces Class A (automated read-only), Class B (human approval required),
and Class C (permanently denied) action boundaries.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ActionClass(str, Enum):
    CLASS_A = "class_a_automated"
    CLASS_B = "class_b_requires_approval"
    CLASS_C = "class_c_denied"


class PolicyDecision(BaseModel):
    allowed: bool
    action_class: ActionClass
    requires_approval: bool
    reason: str
    action_name: str
    target_device: Optional[str] = None
    target_component: Optional[str] = None


# Strict Classification Sets
CLASS_A_TOOLS = {
    "lookup_device",
    "get_health_metrics",
    "get_recent_events",
    "search_manual",
    "run_diagnostic",
    "create_ticket",
}

CLASS_B_ACTIONS = {
    "replace_drive",
    "restart_service",
}

CLASS_C_ACTIONS = {
    "execute_shell_command",
    "execute_arbitrary_shell_command",
    "force_immediate_reboot",
    "rm_rf_root",
    "wipe_drive_unauthorized",
    "download_external_script",
    "modify_system_binaries",
}


class PolicyEngine:
    """
    Evaluates requested tools and actions against immutable safety rules.
    """

    @staticmethod
    def check(tool_name: str, args: Dict[str, Any], incident_context: Optional[Dict[str, Any]] = None) -> PolicyDecision:
        tool = (tool_name or "").strip()
        incident_context = incident_context or {}

        # 1. Propose action checks (consequential mutations)
        if tool == "propose_action":
            action = str(args.get("action_name", "")).strip().lower()
            target_device = args.get("target_device") or incident_context.get("device_id")
            target_component = args.get("target_component") or incident_context.get("bay_id")

            # Check Class C explicitly
            if action in CLASS_C_ACTIONS or any(c in action for c in ["shell", "bash", "reboot", "rm ", "wipe"]):
                return PolicyDecision(
                    allowed=False,
                    action_class=ActionClass.CLASS_C,
                    requires_approval=False,
                    reason=f"Action '{action}' violates security policy (Class C: arbitrary shell or destructive action prohibited).",
                    action_name=action,
                    target_device=target_device,
                    target_component=target_component,
                )

            # Check Class B
            if action in CLASS_B_ACTIONS:
                return PolicyDecision(
                    allowed=False,  # Cannot execute automatically; held for human supervisor approval
                    action_class=ActionClass.CLASS_B,
                    requires_approval=True,
                    reason=f"Action '{action}' requires supervisor approval under Class B remediation policy.",
                    action_name=action,
                    target_device=target_device,
                    target_component=target_component,
                )

            # Unrecognized action in propose_action -> Deny by default
            return PolicyDecision(
                allowed=False,
                action_class=ActionClass.CLASS_C,
                requires_approval=False,
                reason=f"Unrecognized action '{action}' is denied by default.",
                action_name=action,
                target_device=target_device,
                target_component=target_component,
            )

        # 2. Direct Class C Tool Calls
        if tool in CLASS_C_ACTIONS or any(c in tool.lower() for c in ["shell", "bash", "reboot", "rm ", "wipe"]):
            return PolicyDecision(
                allowed=False,
                action_class=ActionClass.CLASS_C,
                requires_approval=False,
                reason=f"Tool '{tool}' violates security policy (Class C: arbitrary shell or destructive action prohibited).",
                action_name=tool,
                target_device=args.get("device_id") or args.get("target_device"),
                target_component=args.get("bay_id") or args.get("target_component"),
            )

        # 3. Direct Class B Tool Calls
        if tool in CLASS_B_ACTIONS:
            target_device = args.get("device_id") or args.get("target_device") or incident_context.get("device_id")
            target_component = args.get("bay_id") or args.get("target_component") or incident_context.get("bay_id")
            return PolicyDecision(
                allowed=False,
                action_class=ActionClass.CLASS_B,
                requires_approval=True,
                reason=f"Direct action '{tool}' requires supervisor approval under Class B remediation policy.",
                action_name=tool,
                target_device=target_device,
                target_component=target_component,
            )

        # 4. Check Standard Allowlisted Class A Tools
        if tool in CLASS_A_TOOLS:
            # Check for injection or shell arguments passed into tools
            for k, v in args.items():
                if isinstance(v, str):
                    val_lower = v.lower()
                    if any(bad in val_lower for bad in ["rm -rf", "; reboot", "| sh", "bash -c"]):
                        return PolicyDecision(
                            allowed=False,
                            action_class=ActionClass.CLASS_C,
                            requires_approval=False,
                            reason=f"Command injection payload detected in argument '{k}'.",
                            action_name=tool,
                        )

            return PolicyDecision(
                allowed=True,
                action_class=ActionClass.CLASS_A,
                requires_approval=False,
                reason="Safe read-only or diagnostic tool permitted.",
                action_name=tool,
                target_device=args.get("device_id") or args.get("target_device"),
                target_component=args.get("bay_id") or args.get("target_component"),
            )

        # 5. Any unlisted tool -> Deny by default
        return PolicyDecision(
            allowed=False,
            action_class=ActionClass.CLASS_C,
            requires_approval=False,
            reason=f"Tool '{tool}' is not in the authorized tool allowlist.",
            action_name=tool,
        )
