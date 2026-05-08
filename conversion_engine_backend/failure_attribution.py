# conversion_engine_backend/failure_attribution.py
# added after peer's explainer
# passed acceptance check :

'''
python - <<'PY'
from conversion_engine_backend.trace_schema import TurnTrace, ModelStage
from conversion_engine_backend.failure_attribution import resolve_failure

trace = TurnTrace()
trace.model_stage = ModelStage(intent="INTERESTED_BOOK_MEETING", confidence=0.9)
print(resolve_failure(trace).model_dump())
PY
'''

from __future__ import annotations

from conversion_engine_backend.trace_schema import (
    FailureAttribution,
    FailureStage,
    StepStatus,
    TurnTrace,
)


def resolve_failure(trace: TurnTrace) -> FailureAttribution:
    if trace.model_stage is None:
        return FailureAttribution(
            failure_stage=FailureStage.model_intent,
            component="llm",
            step="classify_intent",
            reason="No model intent classification was recorded.",
        )

    for step in trace.execution_steps:
        if step.status in {StepStatus.error, StepStatus.not_found}:
            if step.component in {"hubspot", "cal", "resend"}:
                return FailureAttribution(
                    failure_stage=FailureStage.tool_runtime,
                    component=step.component,
                    step=step.step_name,
                    reason=step.error_message or step.status.value,
                )

    if trace.model_stage.intent == "INTERESTED_BOOK_MEETING":
        if not trace.business_outcome.booking_link_generated:
            return FailureAttribution(
                failure_stage=FailureStage.orchestration,
                component="reply_handler",
                step="cal_link_generation",
                reason=(
                    "Booking intent was detected, but no booking link was generated."
                ),
            )

        if not trace.business_outcome.email_sent:
            return FailureAttribution(
                failure_stage=FailureStage.final_delivery,
                component="resend",
                step="resend_email",
                reason="Booking link was generated, but reply email was not sent.",
            )

    return FailureAttribution()
