# conversion_engine_backend/trace_schema.py

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    success = "success"
    skipped = "skipped"
    not_found = "not_found"
    error = "error"


class FailureStage(str, Enum):
    none = "none"
    model_intent = "model_intent"
    tool_arguments = "tool_arguments"
    tool_runtime = "tool_runtime"
    orchestration = "orchestration"
    external_system = "external_system"
    fallback_missing = "fallback_missing"
    final_delivery = "final_delivery"


class ModelAlternative(BaseModel):
    label: str
    score: Optional[float] = None


class ModelStage(BaseModel):
    intent: str
    confidence: Optional[float] = None
    alternatives: List[ModelAlternative] = Field(default_factory=list)
    prompt_version: str = "reply_classification_v1"
    raw_output: Dict[str, Any] = Field(default_factory=dict)


class ExecutionStep(BaseModel):
    step_name: str
    component: str
    status: StepStatus
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class FailureAttribution(BaseModel):
    failure_stage: FailureStage = FailureStage.none
    component: Optional[str] = None
    step: Optional[str] = None
    reason: Optional[str] = None


class BusinessOutcome(BaseModel):
    booking_link_generated: bool = False
    email_sent: bool = False
    meeting_booked: bool = False
    hubspot_updated: bool = False
    lead_status: Optional[str] = None


class TurnTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    prospect_email: Optional[str] = None
    prospect_reply: Optional[str] = None
    our_last_email_body_present: bool = False

    model_stage: Optional[ModelStage] = None
    required_business_action: Optional[str] = None
    execution_steps: List[ExecutionStep] = Field(default_factory=list)

    fallback_policy: Optional[str] = None
    failure_attribution: FailureAttribution = Field(default_factory=FailureAttribution)
    business_outcome: BusinessOutcome = Field(default_factory=BusinessOutcome)

    final_response: Optional[Dict[str, Any]] = None
    