# services/traced_tools.py
# added after peer's explainer
# passed acceptance check : python -m compileall services/traced_tools.py

from __future__ import annotations

from typing import Any, Dict, Optional

from services import cal_service, email_service, hubspot_service
from services.tool_result import ToolResult


def hubspot_find_contact(email: str) -> ToolResult:
    try:
        contact_id = hubspot_service.find_contact_by_email(email)
        if contact_id:
            return ToolResult(
                tool_name="hubspot_lookup",
                status="success",
                payload={"contact_id": contact_id},
            )
        return ToolResult(
            tool_name="hubspot_lookup",
            status="not_found",
            payload={"email": email},
            error_type="contact_not_found",
            error_message="No HubSpot contact found for email.",
        )
    except Exception as exc:
        return ToolResult(
            tool_name="hubspot_lookup",
            status="error",
            payload={"email": email},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )


def hubspot_get_company(contact_id: str) -> ToolResult:
    try:
        company = hubspot_service.get_contact_property(contact_id, "company")
        return ToolResult(
            tool_name="hubspot_get_company",
            status="success" if company else "not_found",
            payload={"company": company},
            error_type=None if company else "company_missing",
            error_message=None if company else "Company property missing in HubSpot.",
        )
    except Exception as exc:
        return ToolResult(
            tool_name="hubspot_get_company",
            status="error",
            payload={"contact_id": contact_id},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )


def hubspot_update_contact(contact_id: str, properties: Dict[str, Any]) -> ToolResult:
    try:
        success = hubspot_service.update_contact_property(contact_id, properties)
        return ToolResult(
            tool_name="hubspot_update_contact",
            status="success" if success else "error",
            payload={"contact_id": contact_id, "properties": properties},
            error_type=None if success else "hubspot_update_failed",
            error_message=None if success else "HubSpot update returned False.",
        )
    except Exception as exc:
        return ToolResult(
            tool_name="hubspot_update_contact",
            status="error",
            payload={"contact_id": contact_id, "properties": properties},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )


def cal_generate_booking_link(partner_name: str) -> ToolResult:
    try:
        link = cal_service.get_booking_link(partner_name)
        return ToolResult(
            tool_name="cal_link_generation",
            status="success",
            payload={"booking_link": link, "partner_name": partner_name},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="cal_link_generation",
            status="error",
            payload={"partner_name": partner_name},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )


def resend_send_email(to_email: str, subject: str, body: str) -> ToolResult:
    try:
        result = email_service.send_email(to_email=to_email, subject=subject, body=body)
        if isinstance(result, dict) and "error" in result:
            return ToolResult(
                tool_name="resend_email",
                status="error",
                payload={"to_email": to_email, "subject": subject},
                error_type="resend_send_failed",
                error_message=str(result.get("error")),
            )

        return ToolResult(
            tool_name="resend_email",
            status="success",
            payload={"to_email": to_email, "subject": subject, "response": result},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="resend_email",
            status="error",
            payload={"to_email": to_email, "subject": subject},
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        