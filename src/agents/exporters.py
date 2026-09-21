"""Export helpers for clean workflow output and explainability traces."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import WorkflowState


DEBUG_KEYS = {
    "_is_ai_predicted",
    "_llm_generated",
    "_llm_instruction",
    "_llm_raw_template",
    "_matched_instruction",
    "_rag_sourced",
    "_source",
}


def clean_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Return a display/export copy without internal provenance fields."""

    return _strip_debug_fields(copy.deepcopy(workflow))


def build_workflow_trace(state: WorkflowState) -> Dict[str, Any]:
    """Build a compact provenance document for debugging and explanation."""

    workflow = state.workflow if isinstance(state.workflow, dict) else {}
    steps = workflow.get("steps", [])
    return {
        "prompt": state.prompt,
        "status": state.status,
        "confidence": state.confidence,
        "plan": [
            {
                "method": intent.method,
                "object": intent.object,
                "reason": intent.reason,
                "source": intent.source,
            }
            for intent in state.plan
        ],
        "step_provenance": _collect_step_provenance(steps),
        "findings": [
            {
                "severity": finding.severity,
                "code": finding.code,
                "message": finding.message,
                "step_index": finding.step_index,
            }
            for finding in state.findings
        ],
        "repairs": list(state.repairs),
        "agent_traces": [
            {
                "agent": trace.agent,
                "action": trace.action,
                "input_summary": trace.input_summary,
                "output_summary": trace.output_summary,
                "metadata": copy.deepcopy(trace.metadata),
            }
            for trace in state.traces
        ],
    }


def write_clean_workflow(path: str | Path, workflow: Dict[str, Any]) -> Path:
    """Write a clean workflow JSON file and return its path."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(clean_workflow(workflow), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def write_workflow_trace(path: str | Path, state: WorkflowState) -> Path:
    """Write a trace JSON file and return its path."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_workflow_trace(state), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def _strip_debug_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_debug_fields(item)
            for key, item in value.items()
            if not _is_debug_key(key)
        }
    if isinstance(value, list):
        return [_strip_debug_fields(item) for item in value]
    return value


def _is_debug_key(key: Any) -> bool:
    key_text = str(key)
    return key_text.startswith("_") or key_text in DEBUG_KEYS


def _collect_step_provenance(steps: Iterable[Any]) -> List[Dict[str, Any]]:
    provenance: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        record = {
            "step_index": step.get("step_index"),
            "method": step.get("method"),
            "object": step.get("object"),
            "rag_sourced": bool(step.get("_rag_sourced")),
            "ai_predicted": bool(step.get("_is_ai_predicted")),
            "llm_generated": bool(step.get("_llm_generated") or step.get("_llm_raw_template")),
            "matched_instruction": step.get("_matched_instruction", ""),
            "llm_instruction": step.get("_llm_instruction", ""),
            "source": step.get("_source", ""),
        }
        raw_template = step.get("_llm_raw_template")
        if raw_template:
            record["llm_raw_template"] = copy.deepcopy(raw_template)
        provenance.append(record)
    return provenance
