"""
Pydantic Schemas for InfraSight.
Defines data contracts for devices, telemetry, events, manuals, diagnostics,
evidence ledger items, and final structured diagnosis.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceModel(BaseModel):
    device_id: str
    asset_id: str
    model_id: str
    rack_location: str
    serial_number: str
    bay_count: int
    bays: List[str]
    ip_address: str
    status: str
    description: str


class TelemetryRecord(BaseModel):
    source_id: str
    device_id: str
    bay_id: str
    timestamp: str
    drive_model: str
    serial_number: str
    capacity_tb: float
    temperature_c: int
    power_on_hours: int
    reallocated_sectors: int
    current_pending_sectors: int
    predictive_failure: bool
    read_error_rate: int
    smart_status: str
    raid_status: str
    rebuild_progress_pct: Optional[float] = None
    enclosure_power_state: Optional[str] = None


class EventRecord(BaseModel):
    source_id: str
    device_id: str
    timestamp: str
    facility: str
    severity: str
    event_code: str
    message: str


class ManualSection(BaseModel):
    source_id: str
    title: str
    model_id: str
    category: str
    content: str


class DiagnosticRecord(BaseModel):
    diagnostic_id: str
    target_device: str
    target_component: str
    test_type: str
    status: str
    execution_time_s: float
    result_summary: str
    metrics: Dict[str, Any]
    error_code: Optional[str] = None


class ConfidenceEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DiagnosisOutput(BaseModel):
    incident_summary: str = Field(description="Summary of the incident observations and findings")
    suspected_component: str = Field(description="Identified hardware component or subsystem")
    confidence: ConfidenceEnum = Field(description="Categorical confidence level")
    likely_cause: str = Field(description="Evidence-backed root cause determination")
    recommended_action: str = Field(description="Recommended diagnostic or remediation procedure")
    cited_evidence_ids: List[str] = Field(description="Immutable source IDs supporting the conclusion")


class ReliabilityEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELIABLE = "unreliable"


class PixelColorResult(BaseModel):
    detected_color: str  # "amber", "green", "red", "off", "unknown"
    hue_degrees: Optional[float] = None
    saturation: Optional[float] = None
    brightness: Optional[float] = None
    reliability: ReliabilityEnum
    pixel_count_analyzed: int
    bounding_box_used: Optional[List[int]] = None
    notes: str
    is_blinking: Optional[bool] = None


class EvidenceType(str, Enum):
    TELEMETRY = "telemetry"
    EVENT_LOG = "event_log"
    MANUAL = "manual"
    IMAGE_MEASUREMENT = "image_measurement"
    DIAGNOSTIC = "diagnostic"


class EvidenceRecord(BaseModel):
    source_id: str
    evidence_type: EvidenceType
    title: str
    summary: str
    raw_payload: Dict[str, Any]
    timestamp: Optional[str] = None
