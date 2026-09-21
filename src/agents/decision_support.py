"""Decision support utilities for planning and step normalization."""

from __future__ import annotations

import copy
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.interactive.scaffolder import InteractiveScaffolder, TopologyEngine

from .models import VALID_METHODS


STRUCTURAL_RECOMMENDATION_TYPES = {
    "physical_cascade",
    "spatial_cascade",
    "cable_splice_association",
}


@dataclass
class CandidateStep:
    """A candidate next action with provenance and historical support."""

    type: str
    method: str
    object: str
    description: str
    source: str
    support_count: int = 0
    examples: List[Dict[str, Any]] = field(default_factory=list)
    topology_type: str = ""
    planner: str = ""
    planning_category: str = ""

    def to_recommendation(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "method": self.method,
            "object": self.object,
            "description": self.description,
            "source": self.source,
            "support_count": self.support_count,
            "examples": copy.deepcopy(self.examples),
            "topology_type": self.topology_type,
            "planner": self.planner,
            "planning_category": self.planning_category,
        }


@dataclass
class PlanningContext:
    """Current planning anchor passed to planning specialists."""

    current_method: str
    current_object: str


class PlanningSpecialist:
    """Base strategy interface for planner candidate generation."""

    name = "PlanningSpecialist"
    category = "general"

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        raise NotImplementedError


class TopologyCascadePlanner(PlanningSpecialist):
    """Recommends physical/spatial downstream creation paths."""

    name = "TopologyCascadePlanner"
    category = "topology_cascade"

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        candidates: List[CandidateStep] = []
        for rec in TopologyEngine.get_downstream_recommendations(
            context.current_object,
            context.current_method,
        ):
            rec_type = rec.get("type", "")
            if rec_type not in STRUCTURAL_RECOMMENDATION_TYPES:
                continue
            candidates.append(_candidate_from_topology_rec(rec, self))
        return candidates


class CrudLifecyclePlanner(PlanningSpecialist):
    """Recommends create/update/delete lifecycle completion steps."""

    name = "CrudLifecyclePlanner"
    category = "crud_lifecycle"

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        candidates: List[CandidateStep] = []
        for rec in TopologyEngine.get_downstream_recommendations(
            context.current_object,
            context.current_method,
        ):
            if rec.get("type") in {"lifecycle_update", "lifecycle_delete"}:
                candidates.append(_candidate_from_topology_rec(rec, self))
        return candidates


class UiNavigationPlanner(PlanningSpecialist):
    """Recommends UI/navigation actions that can appear in real workflows."""

    name = "UiNavigationPlanner"
    category = "ui_navigation"

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        candidates: List[CandidateStep] = []
        for rec in TopologyEngine.get_downstream_recommendations(
            context.current_object,
            context.current_method,
        ):
            if rec.get("type") == "switch_view":
                candidates.append(_candidate_from_topology_rec(rec, self))
        return candidates


class ValidationPlanner(PlanningSpecialist):
    """Recommends validation/check actions for workflow confidence."""

    name = "ValidationPlanner"
    category = "validation_check"

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        candidates: List[CandidateStep] = []
        for rec in TopologyEngine.get_downstream_recommendations(
            context.current_object,
            context.current_method,
        ):
            if rec.get("type") == "datamodel_check":
                candidates.append(_candidate_from_topology_rec(rec, self))
        return candidates


class HistoricalPatternPlanner(PlanningSpecialist):
    """Recommends adjacent steps mined from historical workflows."""

    name = "HistoricalPatternPlanner"
    category = "historical_pattern"

    def __init__(self, history_index: Optional["HistoricalTransitionIndex"] = None):
        self.history_index = history_index or HistoricalTransitionIndex()

    def recommend(self, context: PlanningContext) -> List[CandidateStep]:
        candidates = self.history_index.recommendations_for(
            context.current_method,
            context.current_object,
        )
        for candidate in candidates:
            candidate.planner = self.name
            candidate.planning_category = self.category
        return candidates


def _candidate_from_topology_rec(
    rec: Dict[str, Any],
    specialist: PlanningSpecialist,
) -> CandidateStep:
    return CandidateStep(
        type=rec.get("type", "topology"),
        method=rec.get("method", ""),
        object=rec.get("object", ""),
        description=rec.get("description", ""),
        source=specialist.category,
        topology_type=rec.get("type", ""),
        planner=specialist.name,
        planning_category=specialist.category,
    )


class HistoricalTransitionIndex:
    """Mines adjacent step transitions from real workflow data."""

    def __init__(
        self,
        step_data_path: str | Path = "data/processed/step_level_data.jsonl",
        max_examples: int = 3,
    ):
        self.step_data_path = Path(step_data_path)
        self.max_examples = max_examples
        self._transitions: Dict[Tuple[str, str], Counter[Tuple[str, str]]] = defaultdict(Counter)
        self._examples: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        self._loaded = False

    def recommendations_for(
        self,
        method: str,
        obj: str,
        limit: int = 5,
    ) -> List[CandidateStep]:
        self._load()
        key = (normalize_method(method), normalize_object(obj))
        ranked = self._transitions.get(key, Counter()).most_common(limit)
        candidates: List[CandidateStep] = []
        for (next_method, next_obj), count in ranked:
            example_key = (*key, next_method, next_obj)
            examples = copy.deepcopy(self._examples.get(example_key, []))
            candidates.append(
                CandidateStep(
                    type="historical_transition",
                    method=next_method,
                    object=next_obj,
                    description=(
                        f"Historical next step [{next_method} {next_obj}] "
                        f"observed after [{method} {obj}] in {count} workflow(s)"
                    ),
                    source="history",
                    support_count=count,
                    examples=examples,
                )
            )
        return candidates

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.step_data_path.exists():
            return

        by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        with self.step_data_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                file_id = row.get("file_id")
                if file_id:
                    by_file[file_id].append(row)

        for file_id, steps in by_file.items():
            steps.sort(key=lambda item: item.get("step_index", 0))
            for prev, nxt in zip(steps, steps[1:]):
                prev_key = (
                    normalize_method(prev.get("method", "")),
                    normalize_object(prev.get("object", "")),
                )
                next_key = (
                    normalize_method(nxt.get("method", "")),
                    normalize_object(nxt.get("object", "")),
                )
                if not prev_key[0] or not prev_key[1] or not next_key[0] or not next_key[1]:
                    continue
                if not _is_recommendable_history_step(*next_key):
                    continue
                self._transitions[prev_key][next_key] += 1
                example_key = (*prev_key, *next_key)
                if len(self._examples[example_key]) < self.max_examples:
                    self._examples[example_key].append(
                        {
                            "file_id": file_id,
                            "from_step": prev.get("step_index"),
                            "to_step": nxt.get("step_index"),
                            "instruction_hint": f"{next_key[0]} {next_key[1]}",
                        }
                    )


class CandidateProvider:
    """Combines candidates from planner specialists."""

    def __init__(
        self,
        history_index: Optional[HistoricalTransitionIndex] = None,
        specialists: Optional[List[PlanningSpecialist]] = None,
    ):
        self.history_index = history_index or HistoricalTransitionIndex()
        self.specialists = specialists or [
            TopologyCascadePlanner(),
            CrudLifecyclePlanner(),
            ValidationPlanner(),
            UiNavigationPlanner(),
            HistoricalPatternPlanner(self.history_index),
        ]

    def get_candidates(self, current_object: str, current_method: str) -> List[Dict[str, Any]]:
        candidates: List[CandidateStep] = []
        context = PlanningContext(
            current_method=normalize_method(current_method),
            current_object=normalize_object(current_object),
        )
        for specialist in self.specialists:
            candidates.extend(specialist.recommend(context))
        return [candidate.to_recommendation() for candidate in self._merge(candidates)]

    @staticmethod
    def _merge(candidates: Iterable[CandidateStep]) -> List[CandidateStep]:
        merged: Dict[Tuple[str, str], CandidateStep] = {}
        for candidate in candidates:
            key = (normalize_method(candidate.method), normalize_object(candidate.object))
            if key not in merged:
                merged[key] = candidate
                continue
            current = merged[key]
            if candidate.source not in current.source.split("+"):
                current.source = f"{current.source}+{candidate.source}"
            current.support_count = max(current.support_count, candidate.support_count)
            if candidate.examples:
                current.examples = (current.examples + candidate.examples)[:3]
            if candidate.topology_type and not current.topology_type:
                current.topology_type = candidate.topology_type
            if candidate.planner and candidate.planner not in current.planner.split("+"):
                current.planner = f"{current.planner}+{candidate.planner}" if current.planner else candidate.planner
            if candidate.planning_category and candidate.planning_category not in current.planning_category.split("+"):
                current.planning_category = (
                    f"{current.planning_category}+{candidate.planning_category}"
                    if current.planning_category
                    else candidate.planning_category
                )
            if candidate.support_count and "observed" not in current.description:
                current.description = f"{current.description} | history support={candidate.support_count}"
        return list(merged.values())


class StepTemplateNormalizer:
    """Converts RAG/LLM/free-form templates into the executable step schema."""

    TOP_LEVEL_KEYS = {
        "module",
        "method",
        "object",
        "database",
        "command",
        "object_id",
        "instruction",
        "test_data",
    }

    def normalize(
        self,
        template: Dict[str, Any],
        intent_method: str,
        intent_object: str,
        scaffolder: InteractiveScaffolder,
        object_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_template = copy.deepcopy(template)
        method = normalize_method(intent_method)
        obj = intent_object
        generated_id = object_id or self._choose_object_id(template, method)
        source_template = (
            raw_template.get("_llm_raw_template")
            if isinstance(raw_template.get("_llm_raw_template"), dict)
            else raw_template
        )
        test_data = self._normalize_test_data(source_template, method, obj, scaffolder, generated_id)

        normalized = {
            "database": str(template.get("database") or scaffolder.database).lstrip(":"),
            "object": obj,
            "object_id": generated_id if method == "Create" else template.get("object_id", "Passed"),
            "module": self._module_for(method, template),
            "method": "Open Object" if method == "Open" else method,
            "command": self._command_for(method, template),
            "test_data": test_data,
            "_llm_raw_template": source_template if template.get("_llm_generated") or template.get("_llm_raw_template") else None,
            "_matched_instruction": template.get("instruction", template.get("_matched_instruction", "")),
        }
        return {key: value for key, value in normalized.items() if value is not None}

    def _normalize_test_data(
        self,
        raw_template: Dict[str, Any],
        method: str,
        obj: str,
        scaffolder: InteractiveScaffolder,
        object_id: str,
    ) -> Dict[str, Any]:
        test_data = raw_template.get("test_data")
        method_key = "editor" if method in {"Open", "Switch", "Run", "Verify"} else method.lower()
        if isinstance(test_data, dict):
            mapped = self._map_test_data_keys(test_data)
            if self._is_usable_test_data(mapped, method_key):
                patched = copy.deepcopy(mapped)
                self._patch_ids(patched, method_key, object_id)
                return patched

        if method in {"Create", "Update", "Delete", "Open"}:
            fallback = scaffolder._generate_test_data_body(obj, method, object_id)
            return fallback

        payload = {
            key: copy.deepcopy(value)
            for key, value in raw_template.items()
            if key not in self.TOP_LEVEL_KEYS and not key.startswith("_")
        }
        return {"llm_generated": payload} if payload else {}

    @staticmethod
    def _map_test_data_keys(test_data: Dict[str, Any]) -> Dict[str, Any]:
        mapped: Dict[str, Any] = {}
        for key, value in test_data.items():
            normalized = normalize_method(key)
            if normalized == "Create":
                mapped["create"] = value
            elif normalized == "Update":
                mapped["update"] = value
            elif normalized == "Delete":
                mapped["delete"] = value
            elif normalized in {"Open", "Switch", "Run", "Verify"}:
                mapped["editor"] = value
            else:
                mapped[key] = value
        return mapped

    @staticmethod
    def _is_usable_test_data(test_data: Dict[str, Any], method_key: str) -> bool:
        block = test_data.get(method_key)
        if not isinstance(block, dict):
            return False
        if method_key in {"create", "update"}:
            return any(str(key).startswith("FLD_CSTM") for key in block)
        return True

    @staticmethod
    def _patch_ids(test_data: Dict[str, Any], method_key: str, object_id: str) -> None:
        block = test_data.get(method_key)
        if method_key in {"create", "update"} and isinstance(block, dict):
            for value in block.values():
                if isinstance(value, dict):
                    value["ID"] = object_id
                    return
        if method_key == "delete" and isinstance(block, dict):
            block["ID"] = object_id

    @staticmethod
    def _choose_object_id(template: Dict[str, Any], method: str) -> str:
        if method == "Create":
            return str(random.randint(86393281400000, 86393281499999))
        return str(template.get("object_id") or "Passed")

    @staticmethod
    def _module_for(method: str, template: Dict[str, Any]) -> str:
        if method in {"Create", "Update", "Delete"}:
            return "Datamodel CRUD"
        return template.get("module") or "Editor(s)"

    @staticmethod
    def _command_for(method: str, template: Dict[str, Any]) -> str:
        if method in {"Create", "Update", "Delete"}:
            return "Execute Datamodel CRUD Testcommand"
        return template.get("command") or "Execute Object Control Testcommand"


def normalize_method(method: Any) -> str:
    raw = str(method or "").strip()
    lowered = raw.lower()
    known_methods = {
        "click oneshot button": "Click Oneshot Button",
        "datamodel check": "Datamodel Check",
        "open object": "Open Object",
        "open object with id": "Open Object with ID",
        "select tab": "Select Tab",
        "select first hv object": "Select first HV object",
        "select second hv object": "Select second HV object",
        "switch spatial context": "Switch Spatial Context",
        "verify field": "Verify Field",
    }
    if lowered in known_methods:
        return known_methods[lowered]
    if "create" in lowered:
        return "Create"
    if "update" in lowered or "modify" in lowered or "edit" in lowered:
        return "Update"
    if "delete" in lowered or "remove" in lowered:
        return "Delete"
    if "open" in lowered or "read" in lowered or "view" in lowered:
        return "Open"
    if "switch" in lowered:
        return "Switch"
    if "verify" in lowered or "check" in lowered:
        return "Verify"
    if "run" in lowered:
        return "Run"
    return raw


def normalize_object(obj: Any) -> str:
    return " ".join(str(obj or "").strip().split())


def _is_recommendable_history_step(method: str, obj: str) -> bool:
    if method not in VALID_METHODS:
        return False
    normalized_object = normalize_object(obj).lower()
    if not normalized_object:
        return False
    return True
