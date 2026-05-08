# conversion_engine_backend/trace_writer.py
# added after peer's explainer
# passed acceptance check : 
'''
python - <<'PY'
from conversion_engine_backend.trace_schema import TurnTrace
from conversion_engine_backend.trace_writer import write_turn_trace

trace = TurnTrace(prospect_email="test@example.com", prospect_reply="yes, send times")
write_turn_trace(trace, "eval/test_trace_log.jsonl")
print("trace written")
PY
'''

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from conversion_engine_backend.trace_schema import TurnTrace


DEFAULT_TRACE_PATH = Path("eval/trace_log.jsonl")


def write_turn_trace(
    trace: TurnTrace,
    path: Optional[str | Path] = None,
) -> None:
    output_path = Path(path) if path else DEFAULT_TRACE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False) + "\n")
        