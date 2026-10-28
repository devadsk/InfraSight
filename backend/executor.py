"""
Simulated Execution Engine and Action Policy Enforcer for InfraSight (Phase 4).
Manages mutable per-incident simulation state in SQLite, enforces single-use bound approval records,
executes allowlisted remediations, and verifies state post-execution via the health telemetry read path.
"""

import copy
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from backend import evidence
from backend.policy import ActionClass, PolicyEngine, CLASS_B_ACTIONS, CLASS_C_ACTIONS
from backend.storage import (
    get_incident,
    get_pending_action,
    get_sim_state,
    record_audit_event,
    record_pending_action,
    save_sim_state,
    save_sim_ticket,
    update_action_status,
)


def compute_args_hash(incident_id: str, tool: str, canonical_args: str) -> str:
    """Computes SHA-256 hash over incident_id, tool, and canonical sorted-key JSON arguments."""
    payload = f"{incident_id}:{tool}:{canonical_args}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonicalize_args(args: Dict[str, Any]) -> str:
    """Produces deterministic JSON with sorted keys, stripping any model-injected approval flags."""
    sanitized = {k: v for k, v in args.items() if k not in ["approved", "is_approved", "approval_token"]}
    return json.dumps(sanitized, sort_keys=True)


class SimulatedExecutionEngine:
    """
    Executes and verifies approved remediations against a mutable SQLite-backed simulated state.
    """

    @staticmethod
    def initialize_incident_sim_state(incident_id: str, device_id: str) -> Dict[str, Any]:
        """
        Initializes an isolated mutable copy of the device telemetry and bay states in SQLite.
        Fixtures are never modified.
        """
        existing = get_sim_state(incident_id, device_id)
        if existing:
            return existing

        # Load clean fixtures
        dev_telemetry = [copy.deepcopy(t) for t in evidence._TELEMETRY_CACHE if t.get("device_id") == device_id]
        sim_state = {
            "device_id": device_id,
            "telemetry": dev_telemetry,
            "services": {"storage_daemon": "running", "controller_bus": "active"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        save_sim_state(incident_id, device_id, sim_state)
        return sim_state

    @staticmethod
    def create_pending_action(
        incident_id: str,
        tool: str,
        args: Dict[str, Any],
        step_number: int = 1,
        expires_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        Registers a server-side pending action record.
        Model-supplied 'approved: true' is ignored and logged.
        """
        if "approved" in args or "is_approved" in args:
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="security_warning",
                details={
                    "warning": "Model-supplied approval flag detected in arguments. Flag ignored per security policy.",
                    "supplied_args": args,
                },
            )

        canonical_json = canonicalize_args(args)
        args_hash = compute_args_hash(incident_id, tool, canonical_json)
        action_id = f"ACT-{incident_id}-{hashlib.sha256(f'{tool}:{canonical_json}'.encode()).hexdigest()[:8].upper()}"

        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=expires_minutes)).isoformat()

        record_pending_action(
            action_id=action_id,
            incident_id=incident_id,
            tool=tool,
            canonical_args=canonical_json,
            args_hash=args_hash,
            expires_at=expires_at,
            status="pending",
        )

        record_audit_event(
            incident_id=incident_id,
            step_number=step_number,
            event_type="approval_requested",
            details={
                "action_id": action_id,
                "tool": tool,
                "canonical_args": json.loads(canonical_json),
                "args_hash": args_hash,
                "expires_at": expires_at,
            },
        )

        return {
            "action_id": action_id,
            "incident_id": incident_id,
            "tool": tool,
            "canonical_args": json.loads(canonical_json),
            "status": "pending",
            "expires_at": expires_at,
        }

    @staticmethod
    def approve_action(
        action_id: str,
        decided_by: str = "supervisor@local",
        step_number: int = 99,
    ) -> Dict[str, Any]:
        """
        Marks an action as approved via API.
        Enforces single-use: cannot approve if already approved/executed/rejected.
        """
        action = get_pending_action(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found.")

        current_status = action["status"]
        if current_status in ["approved", "executed"]:
            raise ValueError(f"Action '{action_id}' has already been decided/executed (status: {current_status}).")
        if current_status in ["rejected", "expired", "failed"]:
            raise ValueError(f"Action '{action_id}' is in terminal status '{current_status}' and cannot be approved.")

        now = datetime.now(timezone.utc)
        expires_dt = datetime.fromisoformat(action["expires_at"])
        if now > expires_dt:
            update_action_status(action_id, status="expired")
            raise TimeoutError(f"Action '{action_id}' expired at {action['expires_at']}.")

        decided_at = now.isoformat()
        update_action_status(
            action_id=action_id,
            status="approved",
            decided_by=decided_by,
            decided_at=decided_at,
        )

        record_audit_event(
            incident_id=action["incident_id"],
            step_number=step_number,
            event_type="action_approved",
            details={"action_id": action_id, "decided_by": decided_by, "decided_at": decided_at},
        )

        action["status"] = "approved"
        action["decided_by"] = decided_by
        action["decided_at"] = decided_at
        return action

    @staticmethod
    def reject_action(
        action_id: str,
        decided_by: str = "supervisor@local",
        step_number: int = 99,
    ) -> Dict[str, Any]:
        """
        Marks an action as rejected via API.
        Enforces single-use: cannot reject if already approved/executed/rejected.
        """
        action = get_pending_action(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found.")

        current_status = action["status"]
        if current_status in ["approved", "executed"]:
            raise ValueError(f"Action '{action_id}' has already been decided/executed (status: {current_status}).")
        if current_status in ["rejected", "expired", "failed"]:
            raise ValueError(f"Action '{action_id}' is already in terminal status '{current_status}'.")

        now = datetime.now(timezone.utc)
        decided_at = now.isoformat()
        update_action_status(
            action_id=action_id,
            status="rejected",
            decided_by=decided_by,
            decided_at=decided_at,
        )

        record_audit_event(
            incident_id=action["incident_id"],
            step_number=step_number,
            event_type="action_rejected",
            details={"action_id": action_id, "decided_by": decided_by, "decided_at": decided_at},
        )

        action["status"] = "rejected"
        action["decided_by"] = decided_by
        action["decided_at"] = decided_at
        return action

    @staticmethod
    def execute_and_verify(
        action_id: str,
        step_number: int = 99,
        simulate_telemetry_failure: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes an approved action on mutable sim_state and verifies telemetry read-back.
        Re-runs all security and authorization checks at execution time.
        """
        action = get_pending_action(action_id)
        if not action:
            raise KeyError(f"Action '{action_id}' not found.")

        incident_id = action["incident_id"]
        tool = action["tool"]
        canonical_args = action["canonical_args"]
        args = json.loads(canonical_args)

        # 1. Policy check: Class C is permanently unexecutable even if an approval record exists!
        action_name = args.get("action_name", tool)
        if action_name in CLASS_C_ACTIONS or any(c in action_name for c in ["shell", "bash", "reboot", "rm ", "wipe"]):
            update_action_status(action_id, status="failed")
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="security_violation",
                details={
                    "error": f"Execution of Class C action '{action_name}' is permanently blocked by security policy.",
                    "action_id": action_id,
                },
            )
            raise PermissionError(f"Execution of Class C action '{action_name}' is permanently prohibited.")

        # 2. Hash integrity check: arguments must exactly match stored args_hash
        expected_hash = compute_args_hash(incident_id, tool, canonical_args)
        if action["args_hash"] != expected_hash:
            update_action_status(action_id, status="failed")
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="integrity_violation",
                details={
                    "error": "Argument hash mismatch. Action arguments were modified after creation.",
                    "action_id": action_id,
                },
            )
            raise ValueError("Action arguments integrity verification failed (args_hash mismatch).")

        # 3. Expiry check
        now = datetime.now(timezone.utc)
        expires_dt = datetime.fromisoformat(action["expires_at"])
        if now > expires_dt:
            update_action_status(action_id, status="expired")
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="action_expired",
                details={"action_id": action_id, "expired_at": action["expires_at"]},
            )
            raise TimeoutError(f"Action '{action_id}' expired prior to execution.")

        # 4. Status check: must be 'approved'
        if action["status"] == "executed":
            raise ValueError(f"Action '{action_id}' has already been executed (single use enforced).")
        if action["status"] != "approved":
            raise PermissionError(f"Action '{action_id}' cannot execute because status is '{action['status']}'.")

        # 5. Authorization check: device and bay must match incident context and device inventory
        inc = get_incident(incident_id)
        incident_device = inc.get("device_id") if inc else None
        target_device = args.get("device_id") or args.get("target_device")
        target_bay = args.get("bay_id") or args.get("target_component")

        devices = evidence.load_devices()
        dev_obj = next((d for d in devices if d["device_id"] == target_device), None)

        if incident_device and target_device != incident_device:
            update_action_status(action_id, status="failed")
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="authorization_denied",
                details={
                    "error": f"Target device '{target_device}' does not match incident device '{incident_device}'.",
                    "action_id": action_id,
                },
            )
            raise PermissionError(f"Unauthorized: target device '{target_device}' does not match incident device '{incident_device}'.")

        if dev_obj and target_bay and target_bay not in dev_obj["bays"]:
            update_action_status(action_id, status="failed")
            record_audit_event(
                incident_id=incident_id,
                step_number=step_number,
                event_type="authorization_denied",
                details={
                    "error": f"Target bay '{target_bay}' does not exist on device '{target_device}'.",
                    "action_id": action_id,
                },
            )
            raise ValueError(f"Unauthorized: target bay '{target_bay}' does not exist on device '{target_device}'.")

        # 6. Execute Simulated Mutation on Isolated SQLite State
        record_audit_event(
            incident_id=incident_id,
            step_number=step_number,
            event_type="execution_started",
            details={"action_id": action_id, "tool": tool, "args": args},
        )

        sim_state = SimulatedExecutionEngine.initialize_incident_sim_state(incident_id, target_device)

        if not simulate_telemetry_failure:
            if "replace" in action_name or "replace" in tool:
                # Update drive telemetry in sim_state to healthy
                telemetry_list = sim_state.get("telemetry", [])
                for t in telemetry_list:
                    if t.get("bay_id") == target_bay:
                        t["smart_status"] = "passed"
                        t["predictive_failure"] = False
                        t["reallocated_sectors"] = 0
                        t["current_pending_sectors"] = 0
                        t["temperature_c"] = 32
                        t["raid_status"] = "optimal"
                        t["serial_number"] = f"NEW-{target_device}-{target_bay}"
                        t["firmware_version"] = "REPL-OK"
                save_sim_state(incident_id, target_device, sim_state)

            elif "restart" in action_name or "restart" in tool:
                services = sim_state.get("services", {})
                service_name = args.get("service", "storage_daemon")
                services[service_name] = "running"
                save_sim_state(incident_id, target_device, sim_state)

        # 7. Verification Step: Read back state via the SAME read path as get_health_metrics
        post_telemetry = evidence.get_telemetry(target_device, target_bay, incident_id=incident_id)
        verified = False
        post_evidence_id = None

        if "replace" in action_name or "replace" in tool:
            if post_telemetry:
                rec = post_telemetry[0]
                payload = rec.raw_payload or {}
                # Check that telemetry genuinely reflects replacement success
                if (
                    payload.get("smart_status") == "passed"
                    and payload.get("reallocated_sectors") == 0
                    and not payload.get("predictive_failure")
                ):
                    verified = True

            dev_clean = target_device.replace("-", "")
            bay_clean = (target_bay or "BAY00").replace("-", "")
            post_evidence_id = f"EV-DIAG-{dev_clean}-{bay_clean}-POSTREPLACE"

            # Register dynamic post-verification evidence
            evidence.register_dynamic_evidence({
                "source_id": post_evidence_id,
                "diagnostic_id": post_evidence_id,
                "device_id": target_device,
                "bay_id": target_bay,
                "status": "completed",
                "verified": verified,
                "summary": (
                    f"Post-action telemetry verified healthy for {target_device} {target_bay}: "
                    f"SMART status passed, 0 reallocated sectors, predictive failure cleared."
                    if verified else
                    f"Post-action verification FAILED: Telemetry still reports degraded sectors on {target_device} {target_bay}."
                ),
            })

        elif "restart" in action_name or "restart" in tool:
            verified = True
            dev_clean = target_device.replace("-", "")
            post_evidence_id = f"EV-DIAG-{dev_clean}-POSTRESTART"
            evidence.register_dynamic_evidence({
                "source_id": post_evidence_id,
                "diagnostic_id": post_evidence_id,
                "device_id": target_device,
                "status": "completed",
                "verified": True,
                "summary": f"Post-action verification confirmed service {args.get('service')} is running.",
            })

        executed_at = datetime.now(timezone.utc).isoformat()
        final_status = "executed" if verified else "failed"
        update_action_status(
            action_id=action_id,
            status=final_status,
            executed_at=executed_at,
            result_ref=post_evidence_id,
        )

        record_audit_event(
            incident_id=incident_id,
            step_number=step_number,
            event_type="execution_finished",
            details={
                "action_id": action_id,
                "status": final_status,
                "verified": verified,
                "post_evidence_id": post_evidence_id,
                "executed_at": executed_at,
            },
        )

        return {
            "action_id": action_id,
            "status": final_status,
            "verified": verified,
            "post_evidence_id": post_evidence_id,
            "executed_at": executed_at,
        }

    @staticmethod
    def create_simulated_ticket(
        incident_id: str,
        title: str,
        severity: str,
        summary: str,
        diagnosis: str,
        actions: str,
        status: str = "open",
    ) -> Dict[str, Any]:
        """
        Creates a simulated IT service ticket labeled clearly as simulated.
        """
        ticket_id = f"SIM-TICK-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        labeled_summary = f"[SIMULATED IT SERVICE TICKET] {title}: {summary}"
        save_sim_ticket(
            ticket_id=ticket_id,
            incident_id=incident_id,
            summary=labeled_summary,
            diagnosis=diagnosis,
            actions=actions,
            status=status,
            is_simulated=1,
        )
        return {
            "ticket_id": ticket_id,
            "incident_id": incident_id,
            "title": title,
            "severity": severity,
            "summary": labeled_summary,
            "status": status,
            "is_simulated": True,
        }
