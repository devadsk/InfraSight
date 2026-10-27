"""
Unit and Mocked Test Suite for Phase 3 Investigation Loop.
Tests bounded step limits, tool rejection, policy enforcement,
hallucination downgrading, ambiguous device stopping, model-restricted manual retrieval,
and hero scenario 2 contradiction handling without live API calls.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from backend.meta_client import MetaClient
from backend.orchestrator import InvestigationOrchestrator
from backend.policy import ActionClass, PolicyEngine
from backend.schemas import InvestigationStatus, Diagnosis
from backend.tools import ToolDispatcher
from backend.verifier import DeterministicVerifier


# ---------------------------------------------------------------------------
# 1. TEST POLICY ENGINE: CLASS A, B, AND C BOUNDARIES
# ---------------------------------------------------------------------------

def test_policy_class_a_allowed():
    dec = PolicyEngine.check("get_health_metrics", {"device_id": "SRV-004", "bay_id": "BAY-04"})
    assert dec.allowed is True
    assert dec.action_class == ActionClass.CLASS_A
    assert dec.requires_approval is False


def test_policy_class_b_held_for_approval():
    # Replace physical drive requires supervisor approval
    dec = PolicyEngine.check(
        "propose_action",
        {"action_name": "replace_physical_drive", "target_device": "SRV-004", "justification": "Media degradation"}
    )
    assert dec.allowed is False
    assert dec.action_class == ActionClass.CLASS_B
    assert dec.requires_approval is True
    assert "supervisor approval" in dec.reason.lower()


def test_policy_class_c_permanently_denied():
    # Arbitrary shell execution or destructive action
    for bad_action in ["execute_shell_command", "force_immediate_reboot", "rm_rf_root", "wipe_drive_unauthorized"]:
        dec = PolicyEngine.check(
            "propose_action",
            {"action_name": bad_action, "target_device": "SRV-004", "justification": "Log instruction"}
        )
        assert dec.allowed is False
        assert dec.action_class == ActionClass.CLASS_C
        assert dec.requires_approval is False
        assert "violates security policy" in dec.reason.lower()


def test_policy_injection_payload_in_tool_args_blocked():
    dec = PolicyEngine.check(
        "lookup_device",
        {"device_id": "SRV-004; rm -rf /; reboot"}
    )
    assert dec.allowed is False
    assert dec.action_class == ActionClass.CLASS_C


# ---------------------------------------------------------------------------
# 2. TEST TOOL DISPATCHER & VALIDATION
# ---------------------------------------------------------------------------

def test_tool_dispatcher_unknown_tool_rejected():
    dispatcher = ToolDispatcher()
    res, is_err = dispatcher.dispatch("unauthorized_dangerous_tool", {"arg": "val"})
    assert is_err is True
    assert res.get("status") == "policy_denied"


def test_tool_dispatcher_invalid_args_rejected():
    dispatcher = ToolDispatcher()
    # get_health_metrics requires both device_id and bay_id
    res, is_err = dispatcher.dispatch("get_health_metrics", {"device_id": "SRV-004"})
    assert is_err is True
    assert res.get("status") == "invalid_arguments"


def test_tool_dispatcher_model_restricted_manual_retrieval():
    dispatcher = ToolDispatcher()
    # Search for solid amber on Model X
    res_x, err_x = dispatcher.dispatch(
        "search_manual",
        {"query": "solid amber", "model_id": "SYNTH-SERVER-X"}
    )
    assert err_x is False
    assert len(res_x["sections"]) >= 1
    assert res_x["sections"][0]["source_id"] == "MAN-LED-01"

    # Search for solid amber on Model Y
    res_y, err_y = dispatcher.dispatch(
        "search_manual",
        {"query": "solid amber", "model_id": "SYNTH-SERVER-Y"}
    )
    assert err_y is False
    assert len(res_y["sections"]) >= 1
    assert res_y["sections"][0]["source_id"] == "MAN-LED-02"
    assert "power mode mismatch" in res_y["sections"][0]["content"].lower()


# ---------------------------------------------------------------------------
# 3. TEST DETERMINISTIC VERIFIER
# ---------------------------------------------------------------------------

def test_verifier_hallucinated_source_id_downgraded():
    registered = {"EV-TEL-SRV004-BAY04-S2"}
    raw_diag = {
        "incident_id": "INC-TEST-01",
        "device_id": "SRV-004",
        "status": "confirmed",
        "confidence": "high",
        "summary": "Drive failed media read test.",
        "reasoning": "Uncorrectable LBA error detected.",
        "supporting_evidence_ids": ["EV-TEL-SRV004-BAY04-S2", "EV-TEL-INVENTED-999"],
        "contradictory_evidence_ids": [],
    }

    v_res = DeterministicVerifier.verify(raw_diag, registered)
    assert v_res.downgraded is True
    assert "EV-TEL-INVENTED-999" in v_res.invented_ids
    # Status downgraded from confirmed to more_evidence_required
    assert v_res.verified_diagnosis.status == InvestigationStatus.MORE_EVIDENCE_REQUIRED
    assert v_res.verified_diagnosis.confidence == "low"


def test_verifier_unregistered_source_id_downgraded():
    # ID exists in DB (MAN-LED-01) but was never retrieved for this incident
    registered = {"EV-TEL-SRV004-BAY04-S2"}
    raw_diag = {
        "incident_id": "INC-TEST-02",
        "device_id": "SRV-004",
        "status": "confirmed",
        "confidence": "high",
        "summary": "Drive failed media read test.",
        "reasoning": "Uncorrectable LBA error detected.",
        "supporting_evidence_ids": ["EV-TEL-SRV004-BAY04-S2", "MAN-LED-01"],
        "contradictory_evidence_ids": [],
    }

    v_res = DeterministicVerifier.verify(raw_diag, registered)
    assert v_res.downgraded is True
    assert "MAN-LED-01" in v_res.unregistered_ids
    assert v_res.verified_diagnosis.status == InvestigationStatus.MORE_EVIDENCE_REQUIRED


def test_verifier_resolved_in_simulation_without_execution_downgraded():
    registered = {"EV-TEL-SRV004-BAY04-S2"}
    raw_diag = {
        "incident_id": "INC-TEST-03",
        "device_id": "SRV-004",
        "status": "resolved_in_simulation",
        "confidence": "high",
        "summary": "Resolved drive failure.",
        "reasoning": "Action executed.",
        "supporting_evidence_ids": ["EV-TEL-SRV004-BAY04-S2"],
        "contradictory_evidence_ids": [],
    }

    # simulated_execution_verified is False
    v_res = DeterministicVerifier.verify(raw_diag, registered, simulated_execution_verified=False)
    assert v_res.downgraded is True
    assert v_res.verified_diagnosis.status != InvestigationStatus.RESOLVED_IN_SIMULATION


# ---------------------------------------------------------------------------
# 4. TEST ORCHESTRATOR WITH SCRIPTED MOCK MODEL
# ---------------------------------------------------------------------------

def test_orchestrator_ambiguous_device_stops_for_clarification():
    mock_client = MagicMock(spec=MetaClient)
    orchestrator = InvestigationOrchestrator(meta_client=mock_client)

    # User input lacks specific server ID
    diag, v_res, _ = orchestrator.investigate(
        incident_id="INC-AMBIGUOUS-01",
        user_text="Server in rack 3 has an amber warning light, please investigate.",
    )

    assert diag.status == InvestigationStatus.NEEDS_CLARIFICATION
    assert "ambiguous" in diag.summary.lower()
    # Mock client should not have been called for investigation steps
    assert mock_client.chat_completion.call_count == 0


def test_orchestrator_step_limit_enforced():
    """
    Simulates a loop where the model repeatedly requests tools without stopping.
    The orchestrator must stop at max 6 steps.
    """
    mock_client = MagicMock(spec=MetaClient)

    def mock_chat_completion(*args, **kwargs):
        purpose = kwargs.get("purpose", "")
        if "investigation_step" in purpose:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "call_mock_lookup",
                                    "function": {
                                        "name": "lookup_device",
                                        "arguments": json.dumps({"device_id": "SRV-004"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }, True
        elif purpose == "final_diagnosis":
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "incident_id": "INC-STEP-LIMIT",
                                "device_id": "SRV-004",
                                "status": "unresolved",
                                "confidence": "medium",
                                "summary": "Step limit reached during investigation.",
                                "reasoning": "Telemetry retrieved but investigation bounded by step limit.",
                                "supporting_evidence_ids": [],
                                "contradictory_evidence_ids": [],
                            }),
                        }
                    }
                ]
            }, True
        return {}, True

    mock_client.chat_completion.side_effect = mock_chat_completion
    orchestrator = InvestigationOrchestrator(meta_client=mock_client, max_steps=6)

    diag, v_res, _ = orchestrator.investigate(
        incident_id="INC-STEP-LIMIT",
        user_text="Inspect SRV-004 drive bay 4 status.",
    )

    # 6 investigation steps + 1 final diagnosis call = 7 calls max
    assert mock_client.chat_completion.call_count == 7
    assert diag.status == InvestigationStatus.UNRESOLVED


def test_hero_scenario_2_rebuild_contradiction_ends_not_confirmed():
    """
    Hero Scenario 2 (SCN-02):
    SRV-001 Bay 02 shows solid amber LED.
    Telemetry shows 0 errors, array is in rebuild state (rebuild_in_progress=True).
    Per MAN-LED-01, blinking/solid amber during rebuild is NORMAL.
    Diagnosis must be NOT_CONFIRMED, and physical drive replacement must NOT be executed.
    """
    mock_client = MagicMock(spec=MetaClient)

    call_counter = [0]

    def mock_flow(*args, **kwargs):
        purpose = kwargs.get("purpose", "")
        call_counter[0] += 1

        if purpose == "investigation_step_1":
            # Step 1: Model requests health metrics for SRV-001 BAY-02
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "function": {
                                        "name": "get_health_metrics",
                                        "arguments": json.dumps({"device_id": "SRV-001", "bay_id": "BAY-02"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }, True

        elif purpose == "investigation_step_2":
            # Step 2: Model requests vendor manual for solid amber
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "c2",
                                    "function": {
                                        "name": "search_manual",
                                        "arguments": json.dumps({"query": "solid amber", "model_id": "SYNTH-SERVER-X"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }, True

        elif purpose == "investigation_step_3":
            # Model concludes gathering
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Sufficient evidence collected. Telemetry confirms array rebuild in progress.",
                        }
                    }
                ]
            }, True

        elif purpose == "final_diagnosis":
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "incident_id": "SCN-02",
                                "device_id": "SRV-001",
                                "component_id": "BAY-02",
                                "status": "not_confirmed",
                                "confidence": "high",
                                "summary": "Physical drive is healthy. Amber LED is caused by ongoing background array rebuild, not drive failure.",
                                "reasoning": "SMART telemetry shows zero reallocated sectors and rebuild_in_progress=True. Per MAN-LED-01, amber state during rebuild is normal.",
                                "decision_summary": [
                                    "Correlated amber LED with telemetry indicating rebuild in progress.",
                                    "Refuted drive failure hypothesis; drive replacement averted."
                                ],
                                "supporting_evidence_ids": [
                                    "EV-TEL-SRV001-BAY02-S1",
                                    "MAN-LED-01"
                                ],
                                "contradictory_evidence_ids": [],
                            }),
                        }
                    }
                ]
            }, True

        return {}, True

    mock_client.chat_completion.side_effect = mock_flow
    orchestrator = InvestigationOrchestrator(meta_client=mock_client)

    diag, v_res, _ = orchestrator.investigate(
        incident_id="SCN-02",
        user_text="Technician reports amber LED on SRV-001 BAY-02. Suspects failed drive.",
    )

    assert diag.status == InvestigationStatus.NOT_CONFIRMED
    assert diag.confidence == "high"
    assert "not drive failure" in diag.summary.lower() or "rebuild" in diag.summary.lower()
    assert v_res.is_valid is True
    assert v_res.downgraded is False
