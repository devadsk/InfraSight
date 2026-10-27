"""
Deterministic Verifier for InfraSight (Phase 3).
Validates diagnoses produced by the AI model:
1. Every cited source ID resolves via resolve_source_id() AND was registered during this incident.
2. At least one supporting source must be non-model (telemetry, log, manual, or physical measurement).
3. Contradictory evidence must be preserved.
4. Unsupported conclusions are automatically downgraded.
5. Final status must never be 'resolved_in_simulation' without a verified simulated execution result.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from backend import evidence
from backend.schemas import InvestigationStatus, Diagnosis


class VerificationResult:
    def __init__(
        self,
        is_valid: bool,
        verified_diagnosis: Diagnosis,
        downgraded: bool = False,
        reasons: Optional[List[str]] = None,
        invented_ids: Optional[List[str]] = None,
        unregistered_ids: Optional[List[str]] = None,
    ):
        self.is_valid = is_valid
        self.verified_diagnosis = verified_diagnosis
        self.downgraded = downgraded
        self.reasons = reasons or []
        self.invented_ids = invented_ids or []
        self.unregistered_ids = unregistered_ids or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "downgraded": self.downgraded,
            "reasons": self.reasons,
            "invented_ids": self.invented_ids,
            "unregistered_ids": self.unregistered_ids,
            "final_status": self.verified_diagnosis.status.value,
            "confidence": self.verified_diagnosis.confidence,
        }


class DeterministicVerifier:
    @staticmethod
    def verify(
        raw_diagnosis_dict: Dict[str, Any],
        registered_incident_ids: Set[str],
        simulated_execution_verified: bool = False,
    ) -> VerificationResult:
        reasons: List[str] = []
        invented_ids: List[str] = []
        unregistered_ids: List[str] = []
        downgrade_needed = False

        # 1. Parse or sanitize into Diagnosis schema
        try:
            # Map legacy status strings if any
            status_val = raw_diagnosis_dict.get("status")
            if status_val == "resolved":
                status_val = "resolved_in_simulation"
            raw_diagnosis_dict["status"] = status_val

            diagnosis = Diagnosis(**raw_diagnosis_dict)
        except Exception as e:
            # Schema parse failure fails safe to more_evidence_required
            reasons.append(f"Diagnosis schema validation error: {str(e)}")
            fallback = Diagnosis(
                incident_id=raw_diagnosis_dict.get("incident_id", "INC-UNKNOWN"),
                device_id=raw_diagnosis_dict.get("device_id", "UNKNOWN"),
                status=InvestigationStatus.MORE_EVIDENCE_REQUIRED,
                confidence="low",
                summary="Diagnosis failed strict schema validation; defaulting to more_evidence_required.",
                reasoning="Schema error occurred during model output validation.",
                supporting_evidence_ids=[],
                contradictory_evidence_ids=[],
            )
            return VerificationResult(
                is_valid=False,
                verified_diagnosis=fallback,
                downgraded=True,
                reasons=reasons,
            )

        # 2. Check each supporting evidence ID
        valid_supporting_ids = []
        has_non_model_source = False

        for sid in diagnosis.supporting_evidence_ids:
            # Check if resolves
            try:
                evidence.resolve_source_id(sid)
            except KeyError:
                invented_ids.append(sid)
                reasons.append(f"Cited evidence ID '{sid}' does not exist in authoritative backend.")
                downgrade_needed = True
                continue

            # Check if registered for this incident
            if sid not in registered_incident_ids:
                unregistered_ids.append(sid)
                reasons.append(f"Cited evidence ID '{sid}' exists in system but was not retrieved during this incident.")
                downgrade_needed = True
                continue

            valid_supporting_ids.append(sid)

            # Check if non-model source (telemetry, event, manual, measurement)
            if sid.startswith(("EV-TEL-", "EV-LOG-", "MAN-", "EV-IMG-", "EV-DIAG-")):
                has_non_model_source = True

        # 3. Check contradictory evidence IDs
        valid_contradictory_ids = []
        for cid in diagnosis.contradictory_evidence_ids:
            try:
                evidence.resolve_source_id(cid)
                if cid in registered_incident_ids:
                    valid_contradictory_ids.append(cid)
            except KeyError:
                pass

        # 4. Enforce non-model supporting source requirement
        if not has_non_model_source and diagnosis.status in (InvestigationStatus.CONFIRMED, InvestigationStatus.RESOLVED_IN_SIMULATION):
            reasons.append("Diagnosis lacks at least one authoritative non-model supporting source.")
            downgrade_needed = True

        # 5. Check 'resolved_in_simulation' requirement
        if diagnosis.status == InvestigationStatus.RESOLVED_IN_SIMULATION and not simulated_execution_verified:
            reasons.append("Status 'resolved_in_simulation' claimed without verified post-execution simulation result.")
            downgrade_needed = True

        # 6. Apply downgrade if necessary
        new_status = diagnosis.status
        new_confidence = diagnosis.confidence

        if downgrade_needed:
            if diagnosis.status in (InvestigationStatus.CONFIRMED, InvestigationStatus.RESOLVED_IN_SIMULATION):
                new_status = InvestigationStatus.MORE_EVIDENCE_REQUIRED
            new_confidence = "low"
            reasons.append(f"Confidence downgraded to 'low' and status adjusted to '{new_status.value}' due to unverified claims.")

        verified_diag = diagnosis.model_copy(update={
            "status": new_status,
            "confidence": new_confidence,
            "supporting_evidence_ids": valid_supporting_ids,
            "contradictory_evidence_ids": valid_contradictory_ids,
        })

        return VerificationResult(
            is_valid=not downgrade_needed,
            verified_diagnosis=verified_diag,
            downgraded=downgrade_needed,
            reasons=reasons,
            invented_ids=invented_ids,
            unregistered_ids=unregistered_ids,
        )
