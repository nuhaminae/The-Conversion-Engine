# services/tool_result.py
# added after peer's explainer
# passed acceptance check :

'''
python - <<'PY'
from services.tool_result import ToolResult
print(ToolResult(tool_name="hubspot_lookup", status="not_found").model_dump())
PY
'''


from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class ToolResult(BaseModel):
    tool_name: str
    status: str  # success | not_found | error | skipped
    payload: Dict[str, Any] = {}
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "success"
    