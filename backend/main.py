"""
FastAPI Application for InfraSight (Phase 4).
Exposes REST endpoints for incident lifecycle, agentic investigation,
server-side human approval workflow, and simulated remediation execution.
"""

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.executor import SimulatedExecutionEngine
from backend.meta_client import MetaClient
from backend.orchestrator import InvestigationOrchestrator
from backend.report import generate_incident_markdown_report
from backend.schemas import InvestigationStatus
from backend.storage import (
    get_incident,
    get_incident_audit_trail,
    get_incident_state,
    get_incident_usage,
    get_pending_action,
    get_pending_actions_for_incident,
    get_usage_summary,
    init_db,
    record_audit_event,
    record_incident,
    update_incident_status,
)

from contextlib import asynccontextmanager

UPLOAD_DIR = Path("data/images/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _verify_approver_token(request: Request) -> None:
    """
    Checks optional APPROVER_TOKEN environment variable.
    Protects approval and rejection endpoints in production deployments.
    """
    token_required = os.getenv("APPROVER_TOKEN", "").strip()
    if not token_required:
        return

    # Check Authorization: Bearer <token> or X-Approver-Token header
    auth_header = request.headers.get("Authorization", "").strip()
    provided_token = ""
    if auth_header.startswith("Bearer "):
        provided_token = auth_header[7:].strip()
    elif "X-Approver-Token" in request.headers:
        provided_token = request.headers["X-Approver-Token"].strip()

    if provided_token != token_required:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: invalid or missing approver authentication token.",
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="InfraSight API",
    description="Evidence-first IT Infrastructure Troubleshooting and Safe Remediation Service (Simulated Environment)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str = "simulated"
    version: str = "1.0.0"


class DecisionRequest(BaseModel):
    decided_by: str = "supervisor@local"


# ---------------------------------------------------------------------------
# 1. Health & Meta Information Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Returns service health and operational mode."""
    return HealthResponse()


@app.get("/scenarios")
def list_scenarios() -> List[Dict[str, Any]]:
    """
    Returns sanitized list of synthetic scenarios for picker.
    Exposes only ID, name, description, category, and image frames.
    NEVER exposes expected answers or rubrics.
    Ordered with hero cases first.
    """
    scenarios_path = Path("data/scenarios.json")
    if not scenarios_path.exists():
        return []

    with open(scenarios_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Hero scenario priority order
    hero_order = ["SCN-02", "SCN-01", "SCN-10", "SCN-08", "SCN-03"]
    order_map = {sid: i for i, sid in enumerate(hero_order)}

    sanitized = []
    for scn in data:
        sid = scn.get("scenario_id")
        frames = scn.get("image_frames", [])
        if not frames and scn.get("image_reference"):
            frames = [scn.get("image_reference")]

        sanitized.append({
            "scenario_id": sid,
            "name": scn.get("name"),
            "category": scn.get("category"),
            "incident_description": scn.get("incident_description"),
            "image_reference": scn.get("image_reference"),
            "image_frames": frames,
        })

    sanitized.sort(key=lambda s: order_map.get(s["scenario_id"], 999))
    return sanitized


@app.get("/usage/summary")
def get_usage_summary_endpoint() -> Dict[str, Any]:
    """Cumulative tokens, cost, and call counts from usage ledger."""
    return get_usage_summary()


# ---------------------------------------------------------------------------
# 2. Incident Ingestion
# ---------------------------------------------------------------------------

@app.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(
    description: str = Form(..., description="Technician report or alert description"),
    images: List[UploadFile] = File(default=[], description="Chassis or LED indicator photos"),
    image_paths: Optional[str] = Form(default=None, description="Pre-existing image paths (JSON list)"),
    mode: str = Form(default="live", description="Execution mode: 'live' or 'replay'"),
) -> Dict[str, Any]:
    """
    Creates a new troubleshooting incident with description and optional hardware photos.
    Validates file format and enforces 10MB size limit.
    """
    if not description or not description.strip():
        raise HTTPException(status_code=422, detail="Incident description cannot be empty.")

    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    saved_image_paths: List[str] = []

    if image_paths:
        try:
            parsed = json.loads(image_paths)
            if isinstance(parsed, list):
                saved_image_paths.extend(parsed)
        except Exception:
            pass

    for img in images:
        if not img.filename:
            continue
        ext = Path(img.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported file type '{ext}'. Allowed types: {list(ALLOWED_EXTENSIONS)}",
            )

        content = await img.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=422,
                detail=f"File '{img.filename}' exceeds 10MB limit ({len(content)} bytes).",
            )

        # Magic bytes validation: real PNG or JPEG header
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        if not (is_png or is_jpeg):
            raise HTTPException(
                status_code=422,
                detail=f"File '{img.filename}' failed magic byte validation: content must be real PNG or JPEG image.",
            )

        safe_filename = f"{incident_id}_{uuid.uuid4().hex[:6]}{ext}"
        destination = UPLOAD_DIR / safe_filename
        with open(destination, "wb") as f:
            f.write(content)
        saved_image_paths.append(str(destination).replace("\\", "/"))

    record_incident(
        incident_id=incident_id,
        user_text=description.strip(),
        image_paths=saved_image_paths,
        final_status="created",
        mode=mode,
    )

    record_audit_event(
        incident_id=incident_id,
        step_number=0,
        event_type="incident_created",
        details={"description": description.strip(), "image_count": len(saved_image_paths), "mode": mode},
    )

    inc = get_incident(incident_id)
    return {
        "incident_id": incident_id,
        "description": description.strip(),
        "image_paths": saved_image_paths,
        "status": "created",
        "created_at": inc["created_at"] if inc else None,
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# 3. Investigation Execution
# ---------------------------------------------------------------------------

def _run_investigation_worker(incident_id: str, orchestrator: InvestigationOrchestrator):
    inc = get_incident(incident_id)
    if not inc:
        return
    orchestrator.investigate(
        incident_id=incident_id,
        user_text=inc["user_text"],
        image_paths=inc["image_paths"],
    )


@app.post("/incidents/{incident_id}/investigate")
def start_investigation(
    incident_id: str,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="Run synchronously if True (returns full diagnosis)"),
    mode: str = Query(default="live", description="Execution mode: 'live' or 'replay'"),
) -> Dict[str, Any]:
    """
    Kicks off agentic evidence-first investigation.
    Runs asynchronously in background by default, returning immediately.
    """
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    is_replay = (mode == "replay")
    client = MetaClient(replay_mode=is_replay, mock_mode=is_replay)
    orchestrator = InvestigationOrchestrator(meta_client=client)

    if sync:
        update_incident_status(incident_id, final_status="investigating", mode=mode)
        diag, v_res, _ = orchestrator.investigate(
            incident_id=incident_id,
            user_text=inc["user_text"],
            image_paths=inc["image_paths"],
        )
        return {
            "incident_id": incident_id,
            "status": diag.status.value,
            "diagnosis": diag.model_dump(),
            "verification": v_res.to_dict(),
            "mode": mode,
        }

    update_incident_status(incident_id, final_status="investigating", mode=mode)
    background_tasks.add_task(_run_investigation_worker, incident_id, orchestrator)

    return {
        "incident_id": incident_id,
        "status": "investigating",
        "message": "Investigation started in background.",
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# 4. Incident Details, Report & Timeline
# ---------------------------------------------------------------------------

@app.get("/incidents/{incident_id}")
def get_incident_details(incident_id: str) -> Dict[str, Any]:
    """
    Returns incident status, evidence registry, timeline, diagnosis, pending actions, and usage.
    """
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    audit_trail = get_incident_audit_trail(incident_id)
    pending_actions = get_pending_actions_for_incident(incident_id)
    state = get_incident_state(incident_id)
    usage_info = get_incident_usage(incident_id)

    raw_diag = inc.get("raw_diagnosis") or {}
    supporting_evidence = raw_diag.get("supporting_evidence_ids", [])
    if state and not supporting_evidence:
        supporting_evidence = state.get("evidence_ids", [])

    return {
        "incident_id": incident_id,
        "status": inc["final_status"],
        "created_at": inc["created_at"],
        "device_id": inc["device_id"],
        "bay_id": inc["bay_id"],
        "summary": inc["summary"],
        "confidence": inc["confidence"],
        "diagnosis": raw_diag,
        "pending_actions": pending_actions,
        "timeline": audit_trail,
        "evidence": supporting_evidence,
        "mode": inc.get("mode") or "live",
        "usage": usage_info,
    }


@app.get("/incidents/{incident_id}/report")
def get_incident_report(incident_id: str) -> Dict[str, Any]:
    """Returns final incident post-investigation report as Markdown (Master Spec Step 9)."""
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    md_report = generate_incident_markdown_report(incident_id)
    return {
        "incident_id": incident_id,
        "format": "markdown",
        "report": md_report,
    }


# ---------------------------------------------------------------------------
# 5. Incident Audit Trail
# ---------------------------------------------------------------------------

@app.get("/incidents/{incident_id}/audit")
def get_incident_audit(incident_id: str) -> Dict[str, Any]:
    """Returns complete immutable audit event log for the incident."""
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")

    trail = get_incident_audit_trail(incident_id)
    return {
        "incident_id": incident_id,
        "event_count": len(trail),
        "audit_trail": trail,
    }


# ---------------------------------------------------------------------------
# 6. Action Approval & Execution Loop
# ---------------------------------------------------------------------------

@app.post("/actions/{action_id}/approve")
def approve_action(
    action_id: str,
    request: Request,
    decision: DecisionRequest = DecisionRequest(),
) -> Dict[str, Any]:
    """
    Supervisor approval endpoint.
    Verifies single use, argument integrity, non-expiry, and executes mutation on simulated state.
    Resumes investigation with post-action telemetry read-back.
    """
    _verify_approver_token(request)
    action = get_pending_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    # 1. State / Single Use checks
    if action["status"] in ["approved", "executed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Action '{action_id}' has already been decided or executed (status: '{action['status']}').",
        )
    if action["status"] in ["rejected", "failed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Action '{action_id}' is in terminal status '{action['status']}' and cannot be approved.",
        )
    if action["status"] == "expired":
        raise HTTPException(status_code=410, detail=f"Action '{action_id}' has expired.")

    # 2. Approve Action
    try:
        SimulatedExecutionEngine.approve_action(action_id, decided_by=decision.decided_by)
    except TimeoutError as te:
        raise HTTPException(status_code=410, detail=str(te))
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=422, detail=str(ex))

    # 3. Execute Mutation and Verify Telemetry Read-Back
    try:
        exec_result = SimulatedExecutionEngine.execute_and_verify(action_id)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except (ValueError, TimeoutError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Execution engine failure: {str(ex)}")

    # 4. Resume Investigation with verified evidence
    incident_id = action["incident_id"]
    orchestrator = InvestigationOrchestrator()
    try:
        final_diag, v_res, _ = orchestrator.resume_investigation(
            incident_id=incident_id,
            action_id=action_id,
            decision="approved",
            post_verification=exec_result,
            decided_by=decision.decided_by,
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to resume investigation: {str(ex)}")

    return {
        "action_id": action_id,
        "status": "executed",
        "decided_by": decision.decided_by,
        "verification": exec_result,
        "incident_status": final_diag.status.value,
        "diagnosis": final_diag.model_dump(),
        "mode": "simulated",
    }


# ---------------------------------------------------------------------------
# 7. Action Rejection Loop
# ---------------------------------------------------------------------------

@app.post("/actions/{action_id}/reject")
def reject_action(
    action_id: str,
    request: Request,
    decision: DecisionRequest = DecisionRequest(),
) -> Dict[str, Any]:
    """
    Supervisor rejection endpoint.
    Records supervisor rejection, updates action record, and resumes investigation as 'unresolved'.
    """
    _verify_approver_token(request)
    action = get_pending_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found.")

    if action["status"] in ["approved", "executed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Action '{action_id}' has already been decided or executed (status: '{action['status']}').",
        )
    if action["status"] in ["rejected", "failed"]:
        raise HTTPException(
            status_code=409,
            detail=f"Action '{action_id}' is already rejected or failed (status: '{action['status']}').",
        )
    if action["status"] == "expired":
        raise HTTPException(status_code=410, detail=f"Action '{action_id}' has expired.")

    try:
        SimulatedExecutionEngine.reject_action(action_id, decided_by=decision.decided_by)
    except ValueError as ve:
        raise HTTPException(status_code=409, detail=str(ve))
    except Exception as ex:
        raise HTTPException(status_code=422, detail=str(ex))

    # Resume investigation as unresolved
    incident_id = action["incident_id"]
    orchestrator = InvestigationOrchestrator()
    try:
        final_diag, v_res, _ = orchestrator.resume_investigation(
            incident_id=incident_id,
            action_id=action_id,
            decision="rejected",
            decided_by=decision.decided_by,
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to resume investigation: {str(ex)}")

    return {
        "action_id": action_id,
        "status": "rejected",
        "decided_by": decision.decided_by,
        "incident_status": "unresolved",
        "diagnosis": final_diag.model_dump(),
        "mode": "simulated",
    }
