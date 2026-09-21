"""Default agents used by the GIS workflow loop."""

from __future__ import annotations

import copy
import json
import random
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.interactive.scaffolder import InteractiveScaffolder, TopologyEngine

from .decision_support import (
    CandidateProvider,
    StepTemplateNormalizer,
    STRUCTURAL_RECOMMENDATION_TYPES,
    normalize_method,
)
from .models import Finding, REQUIRED_STEP_KEYS, VALID_METHODS, StepIntent, WorkflowState


STRUCTURAL_VALIDATION_CODES = {
    "missing_steps",
    "total_steps_mismatch",
    "missing_step_key",
    "step_index_mismatch",
    "missing_create_id",
    "test_data_not_object",
}

PLANNING_VALIDATION_CODES = {
    "unknown_method",
    "missing_object",
}

AMBIGUOUS_VALIDATION_CODES = {
    "workflow_not_object",
    "step_not_object",
}


def classify_validation_failure(findings: Iterable[Finding]) -> str:
    """Route validation failures to repair, re-plan, or human review."""

    error_codes = {finding.code for finding in findings if finding.is_error}
    if not error_codes:
        return "review"
    if error_codes.intersection(AMBIGUOUS_VALIDATION_CODES):
        return "human_review"
    if error_codes.intersection(PLANNING_VALIDATION_CODES):
        return "replan"
    if error_codes.issubset(STRUCTURAL_VALIDATION_CODES):
        return "repair"
    return "human_review"


class BaseAgent(ABC):
    """Minimal synchronous agent interface."""

    name = "BaseAgent"

    @abstractmethod
    def run(self, state: WorkflowState) -> WorkflowState:
        """Read and mutate the workflow state."""


class ContextManagerAgent(BaseAgent):
    """Condenses long user context into GIS-specific atomic intents."""

    name = "ContextManagerAgent"

    SPECIAL_METHOD_PATTERNS = [
        ("Click Oneshot Button", r"\bclick\b.*\b(button|insert|delete|update|get|select|lock|clear)\b"),
        ("Datamodel Check", r"\b(datamodel check|consistency check)\b"),
        ("Select Tab", r"\b(select|open)\b.*\btab\b"),
        ("Select first HV object", r"\bselect\b.*\bfirst\b.*\b(hv|hierarchy)\b"),
        ("Select second HV object", r"\bselect\b.*\bsecond\b.*\b(hv|hierarchy)\b"),
        ("Switch Spatial Context", r"\b(switch|change)\b.*\b(spatial context|schema|view)\b"),
        ("Verify Field", r"\b(verify|check)\b.*\b(field|value)\b"),
    ]

    DEFAULT_METHOD_SYNONYMS = {
        "Create": ["create", "insert", "add", "make", "new", "generate", "generating", "generated"],
        "Update": ["update", "modify", "edit", "change"],
        "Delete": ["delete", "remove", "destroy"],
        "Open Object": ["open", "read", "view"],
    }

    DEFAULT_KNOWN_OBJECTS = [
        "E MS Installatie FP",
        "E MS Rail FP",
        "E MS Veld FP Geleider",
        "E MS Veld FP",
        "E MS Eindsluiting FP",
        "E Stationcomplex",
        "E Station Gebouw",
        "E Station Terrein",
        "E MS Kabel",
        "E HS Kabel",
        "E LS Kabel",
        "E MS Mof",
        "E HS Mof",
        "E LS Mof",
        "E MS Verbinding",
        "Elektra;Catalogus",
        "Object Editor",
        "Object Control",
        "Stationsschema",
        "datamodel_check",
        "insert",
        "delete",
        "update",
        "select",
        "get",
        "clear",
        "lock",
    ]

    DEFAULT_OBJECT_ALIASES = {
        "ms cable": "E MS Kabel",
        "medium voltage cable": "E MS Kabel",
        "e ms cable": "E MS Kabel",
        "hs cable": "E HS Kabel",
        "high voltage cable": "E HS Kabel",
        "e hs cable": "E HS Kabel",
        "ls cable": "E LS Kabel",
        "low voltage cable": "E LS Kabel",
        "e ls cable": "E LS Kabel",
        "ms joint": "E MS Mof",
        "hs joint": "E HS Mof",
        "ls joint": "E LS Mof",
    }

    NON_GIS_TERMS = {
        "email",
        "meeting",
        "slide",
        "presentation",
        "resume",
        "cv",
        "report",
        "summarize",
        "explain",
        "translate",
    }

    def __init__(
        self,
        long_prompt_threshold: int = 220,
        synonym_config_path: str | Path = "configs/gis_synonyms.json",
    ):
        self.long_prompt_threshold = long_prompt_threshold
        self.method_patterns, self.known_objects, self.object_aliases = self._load_synonym_config(
            synonym_config_path
        )

    def run(self, state: WorkflowState) -> WorkflowState:
        state.original_prompt = state.original_prompt or state.prompt
        candidates = self._extract_candidates(state.prompt)

        if not candidates:
            state.condensed_prompt = state.prompt
            state.add_trace(
                self.name,
                "pass_through",
                self._preview(state.prompt),
                "No GIS-specific context condensation needed.",
                {"reason": "no_candidate"},
            )
            return state

        selected = self._select_candidates(candidates)
        state.context_intents = [
            StepIntent(
                method=item["method"],
                object=item["object"],
                reason=f"Extracted from user context: {item['sentence']}",
                source="context_manager",
            )
            for item in selected
        ]
        state.condensed_prompt = "; ".join(
            f"{intent.method} {intent.object}" for intent in state.context_intents
        )
        state.prompt = state.condensed_prompt
        state.runtime["context_condensed"] = (
            state.condensed_prompt.strip().lower() != state.original_prompt.strip().lower()
        )

        if len(candidates) > len(selected):
            state.context_warnings.append(
                f"Ignored {len(candidates) - len(selected)} lower-confidence GIS-like sentence(s)."
            )
        if len(selected) > 1:
            state.context_warnings.append(
                "Multiple GIS intents were extracted from the prompt."
            )

        state.add_trace(
            self.name,
            "condense",
            self._preview(state.original_prompt),
            f"Extracted {len(state.context_intents)} GIS intent(s).",
            {
                "condensed_prompt": state.condensed_prompt,
                "selected": selected,
                "candidates": candidates,
                "warnings": list(state.context_warnings),
            },
        )
        return state

    def _extract_candidates(self, prompt: str) -> List[Dict[str, Any]]:
        sentences = self._split_sentences(prompt)
        candidates: List[Dict[str, Any]] = []
        for sentence in sentences:
            method = self._detect_method(sentence)
            obj = self._detect_object(sentence)
            score = self._score_sentence(sentence, method, obj)
            if method and obj and score >= 4:
                candidates.append(
                    {
                        "sentence": sentence.strip(),
                        "method": method,
                        "object": obj,
                        "score": score,
                    }
                )
        return candidates

    def _select_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)
        best_score = candidates[0]["score"]
        selected = [
            item for item in candidates if item["score"] >= best_score - 1 and item["score"] >= 5
        ]
        if len(selected) == 1:
            return selected
        unique: Dict[tuple[str, str], Dict[str, Any]] = {}
        for item in selected:
            unique.setdefault((item["method"], item["object"]), item)
        return list(unique.values())

    @staticmethod
    def _split_sentences(prompt: str) -> List[str]:
        pieces = re.split(r"[\n.;]+|\b(?:and then|then|after that)\b", prompt, flags=re.IGNORECASE)
        return [piece.strip() for piece in pieces if piece.strip()]

    def _detect_method(self, sentence: str) -> str:
        lowered = sentence.lower()
        for method, pattern in self.method_patterns:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                return method
        return ""

    def _detect_object(self, sentence: str) -> str:
        lowered = sentence.lower()
        for alias, obj in self.object_aliases:
            if re.search(self._phrase_pattern(alias), lowered, flags=re.IGNORECASE):
                return obj
        for obj in self.known_objects:
            if obj.lower() in lowered:
                return obj
        matched = re.search(
            r"(E\s+(?:HS|MS|LS)\s+[^,.;]+?)(?:\s+where|\s+in\s+|$)",
            sentence,
            re.IGNORECASE,
        )
        return matched.group(1).strip() if matched else ""

    @classmethod
    def _load_synonym_config(
        cls,
        config_path: str | Path,
    ) -> tuple[List[tuple[str, str]], List[str], List[tuple[str, str]]]:
        method_synonyms = copy.deepcopy(cls.DEFAULT_METHOD_SYNONYMS)
        known_objects = list(cls.DEFAULT_KNOWN_OBJECTS)
        object_aliases = dict(cls.DEFAULT_OBJECT_ALIASES)

        path = Path(config_path)
        if path.exists():
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
                method_synonyms.update(config.get("method_synonyms", {}))
                for obj in config.get("known_objects", []):
                    if obj not in known_objects:
                        known_objects.append(obj)
                for canonical, aliases in config.get("object_aliases", {}).items():
                    if canonical not in known_objects:
                        known_objects.append(canonical)
                    for alias in aliases:
                        object_aliases[str(alias).lower()] = canonical
            except (OSError, json.JSONDecodeError, TypeError):
                pass

        method_patterns = list(cls.SPECIAL_METHOD_PATTERNS)
        synonym_patterns: List[tuple[str, str]] = []
        for method, aliases in method_synonyms.items():
            for alias in aliases:
                phrase = str(alias).strip().lower()
                if phrase:
                    synonym_patterns.append((method, cls._phrase_pattern(phrase)))
        synonym_patterns.sort(key=lambda item: len(item[1]), reverse=True)
        method_patterns.extend(synonym_patterns)

        alias_pairs = [(alias, obj) for alias, obj in object_aliases.items() if alias]
        alias_pairs.sort(key=lambda item: len(item[0]), reverse=True)
        known_objects.sort(key=len, reverse=True)
        return method_patterns, known_objects, alias_pairs

    @staticmethod
    def _phrase_pattern(phrase: str) -> str:
        escaped = re.escape(phrase.strip().lower()).replace(r"\ ", r"\s+")
        return rf"(?<!\w){escaped}(?!\w)"

    def _score_sentence(self, sentence: str, method: str, obj: str) -> int:
        lowered = sentence.lower()
        score = 0
        if method:
            score += 2
        if obj:
            score += 3
        if any(term in lowered for term in ["gis", "elektra", "datamodel", "station", "schema"]):
            score += 1
        if any(term in lowered for term in self.NON_GIS_TERMS):
            score -= 2
        if len(sentence.split()) > 45:
            score -= 1
        return score

    @staticmethod
    def _preview(text: str, limit: int = 240) -> str:
        compact = " ".join(str(text).split())
        return compact if len(compact) <= limit else compact[: limit - 3] + "..."


class PlannerAgent(BaseAgent):
    """Turns a user request into step-level intents."""

    name = "PlannerAgent"

    def __init__(
        self,
        max_steps: int = 5,
        choice_sequence: Optional[List[int]] = None,
        candidate_provider: Optional[CandidateProvider] = None,
    ):
        self.max_steps = max(1, max_steps)
        self.choice_sequence = choice_sequence or []
        self.candidate_provider = candidate_provider or CandidateProvider()

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.context_intents:
            plan = list(state.context_intents[: self.max_steps])
            anchor_method = plan[-1].method
            anchor_object = plan[-1].object
        else:
            probe = InteractiveScaffolder()
            first_step = probe.parse_and_create_step_one(state.prompt, use_rag=False)
            anchor_method = first_step.get("method", "Create")
            anchor_object = first_step.get("object", "E MS Installatie FP")

            plan = [
                StepIntent(
                    method=anchor_method,
                    object=anchor_object,
                    reason="Seed operation parsed from user prompt.",
                )
            ]
        decisions: List[Dict[str, Any]] = []
        choice_index = 0
        expand_plan = self._should_expand_plan(state)

        while expand_plan and len(plan) < self.max_steps:
            recommendations = self.candidate_provider.get_candidates(
                anchor_object,
                anchor_method,
            )
            selected, decision = self._select_recommendation(
                recommendations,
                anchor_object,
                anchor_method,
                self.choice_sequence[choice_index] if choice_index < len(self.choice_sequence) else None,
            )
            decisions.append(decision)
            choice_index += 1

            if selected is None:
                break

            plan.append(
                StepIntent(
                    method=selected["method"],
                    object=selected["object"],
                    reason=selected.get("description", selected.get("type", "")),
                    source=selected.get("type", "topology"),
                )
            )

            if selected.get("type") in STRUCTURAL_RECOMMENDATION_TYPES:
                anchor_method = selected["method"]
                anchor_object = selected["object"]
            elif selected.get("method") in {"Run", "Switch", "Verify"}:
                break

        state.plan = plan
        state.status = "planned"
        state.add_trace(
            self.name,
            "plan",
            state.prompt,
            f"Planned {len(plan)} step intents.",
            {
                "plan": [intent.__dict__ for intent in plan],
                "decisions": decisions,
                "choice_sequence": self.choice_sequence,
            },
        )
        return state

    @staticmethod
    def _should_expand_plan(state: WorkflowState) -> bool:
        if not state.context_intents:
            return True
        original_prompt = state.original_prompt or state.prompt
        lowered = original_prompt.lower()
        explicit_multi_step = any(
            marker in lowered
            for marker in [
                "full workflow",
                "complete workflow",
                "whole workflow",
                "multi-step",
                "multiple steps",
                "cascade",
                "end-to-end",
                "test case",
                "test script",
            ]
        )
        if explicit_multi_step:
            return True
        return not state.runtime.get("context_condensed", False)

    @staticmethod
    def _select_recommendation(
        recommendations: Iterable[Dict[str, Any]],
        anchor_object: str,
        anchor_method: str,
        explicit_choice: Optional[int] = None,
    ) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        recommendations = list(recommendations)
        primary_recommendations = [
            rec
            for rec in recommendations
            if rec.get("source") != "history"
        ]
        history_recommendations = [
            rec
            for rec in recommendations
            if rec.get("source") == "history"
        ]
        ordered_recommendations = primary_recommendations + history_recommendations
        menu = [
            {
                "choice": idx,
                "method": rec.get("method"),
                "object": rec.get("object"),
                "type": rec.get("type"),
                "description": rec.get("description"),
                "source": rec.get("source"),
                "planner": rec.get("planner"),
                "planning_category": rec.get("planning_category"),
                "support_count": rec.get("support_count", 0),
                "examples": rec.get("examples", []),
            }
            for idx, rec in enumerate(primary_recommendations, start=1)
        ]
        done_choice = len(primary_recommendations) + 1
        history_menu = [
            {
                "choice": idx,
                "method": rec.get("method"),
                "object": rec.get("object"),
                "type": rec.get("type"),
                "description": rec.get("description"),
                "source": rec.get("source"),
                "planner": rec.get("planner"),
                "planning_category": rec.get("planning_category"),
                "support_count": rec.get("support_count", 0),
                "examples": rec.get("examples", []),
            }
            for idx, rec in enumerate(history_recommendations, start=done_choice + 1)
        ]

        decision: Dict[str, Any] = {
            "anchor": {"method": anchor_method, "object": anchor_object},
            "menu": menu + [{"choice": done_choice, "method": "DONE", "object": "", "type": "done", "description": "Finish planning"}] + history_menu,
            "selected_choice": None,
            "selection_source": "auto",
            "selected": None,
        }

        if explicit_choice is not None:
            decision["selected_choice"] = explicit_choice
            decision["selection_source"] = "choice_sequence"
            if explicit_choice == done_choice:
                decision["selected"] = {"type": "done", "description": "User-selected planning stop."}
                return None, decision
            if 1 <= explicit_choice <= len(primary_recommendations):
                selected = primary_recommendations[explicit_choice - 1]
                decision["selected"] = selected
                return selected, decision
            if done_choice < explicit_choice <= done_choice + len(history_recommendations):
                selected = history_recommendations[explicit_choice - done_choice - 1]
                decision["selected"] = selected
                return selected, decision
            decision["selected"] = {"type": "invalid_choice", "description": f"Invalid choice {explicit_choice}; stopped planning."}
            return None, decision

        for rec in primary_recommendations:
            if rec.get("type") in STRUCTURAL_RECOMMENDATION_TYPES or rec.get("topology_type") in STRUCTURAL_RECOMMENDATION_TYPES:
                decision["selected_choice"] = primary_recommendations.index(rec) + 1
                decision["selected"] = rec
                return rec, decision
        for rec in primary_recommendations:
            if rec.get("type") == "lifecycle_update":
                decision["selected_choice"] = primary_recommendations.index(rec) + 1
                decision["selected"] = rec
                return rec, decision
        selected = primary_recommendations[0] if primary_recommendations else (history_recommendations[0] if history_recommendations else None)
        if selected is not None:
            if selected in primary_recommendations:
                decision["selected_choice"] = primary_recommendations.index(selected) + 1
            else:
                decision["selected_choice"] = done_choice + history_recommendations.index(selected) + 1
            decision["selected"] = selected
        return selected, decision


class GeneratorAgent(BaseAgent):
    """Materializes planned intents into executable workflow JSON."""

    name = "GeneratorAgent"

    def __init__(
        self,
        use_rag: bool = False,
        rag_index_dir: str = "data/processed/rag_index",
        load_llm: bool = False,
        model_dir: str = "models/step-level-model-865",
        model_quantization: Optional[str] = None,
        model_backend: str = "transformers",
        llama_server_url: str = "http://127.0.0.1:8080",
    ):
        self.use_rag = use_rag
        self.rag_index_dir = rag_index_dir
        self.load_llm = load_llm
        self.model_dir = model_dir
        self.model_quantization = model_quantization
        self.model_backend = model_backend
        self.llama_server_url = llama_server_url

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.plan:
            state.findings = [
                Finding("error", "missing_plan", "GeneratorAgent received no plan.")
            ]
            state.status = "failed"
            return state

        scaffolder = InteractiveScaffolder()
        rag_loaded = scaffolder.load_rag_engine(self.rag_index_dir) if self.use_rag else False
        llm_loaded = False
        if self.load_llm:
            llm_loaded = self._load_llm(scaffolder)

        first_prompt = f"{state.plan[0].method} {state.plan[0].object}"
        first_step = scaffolder.parse_and_create_step_one(
            first_prompt,
            use_rag=rag_loaded,
        )
        previous_step = first_step

        for intent in state.plan[1:]:
            recommendation = {
                "type": intent.source,
                "object": intent.object,
                "method": intent.method,
                "description": intent.reason,
            }
            previous_step = scaffolder.build_cascade_step(recommendation, previous_step)

        state.workflow = json.loads(scaffolder.get_full_workflow_json())
        state.status = "generated"
        state.add_trace(
            self.name,
            "generate",
            f"{len(state.plan)} planned intents.",
            f"Generated workflow with {len(state.workflow.get('steps', []))} steps.",
            {"rag_loaded": rag_loaded, "llm_loaded": llm_loaded},
        )
        return state

    def _load_llm(self, scaffolder: InteractiveScaffolder) -> bool:
        try:
            if self.model_backend == "llama_cpp_server":
                from src.inference.llama_cpp_predictor import LlamaCppServerPredictor

                scaffolder.llm_predictor = LlamaCppServerPredictor(
                    server_url=self.llama_server_url,
                )
                return True

            from src.inference.step_llm_predictor import StepLevelPredictor

            scaffolder.llm_predictor = StepLevelPredictor(
                model_dir=self.model_dir,
                verbose=False,
                quantization=self.model_quantization,
            )
            return True
        except Exception as exc:
            print(f"[WARN] LLM predictor not available: {exc}")
            scaffolder.llm_predictor = None
            return False


class GenerationInitializerAgent(BaseAgent):
    """Initializes shared generation runtime for the granular graph."""

    name = "GenerationInitializerAgent"

    def __init__(self, runtime: Optional[Dict[str, Any]] = None):
        self.runtime = runtime
        self.normalizer = StepTemplateNormalizer()

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.plan:
            state.findings = [
                Finding("error", "missing_plan", "Generation initializer received no plan.")
            ]
            state.status = "failed"
            return state

        runtime = self._runtime(state)
        runtime["scaffolder"] = InteractiveScaffolder()
        runtime["previous_step"] = None
        state.active_intent_index = 0
        state.active_template = None
        state.active_template_source = ""
        state.generation_complete = False
        state.status = "generation_initialized"
        state.add_trace(
            self.name,
            "initialize",
            f"{len(state.plan)} planned intents.",
            "Created scaffolder runtime for step-by-step graph generation.",
        )
        return state

    def _runtime(self, state: WorkflowState) -> Dict[str, Any]:
        return self.runtime if self.runtime is not None else state.runtime


class RAGReranker:
    """Selects the most materializable RAG template from top-k candidates."""

    METHOD_WEIGHT = 0.25
    OBJECT_WEIGHT = 0.25
    FIELD_WEIGHT = 0.15
    SCHEMA_WEIGHT = 0.10
    RAG_WEIGHT = 0.25

    METHOD_FAMILIES = [
        {"Open Object", "Open Object with ID", "Open"},
        {"Verify", "Verify Field"},
        {"Switch", "Switch Spatial Context"},
        {"Select Tab", "Select first HV object", "Select second HV object"},
    ]

    def select(
        self,
        intent: StepIntent,
        candidates: List[Dict[str, Any]],
        query: str = "",
    ) -> Optional[Dict[str, Any]]:
        ranked = self.rank(intent, candidates, query=query)
        return ranked[0] if ranked else None

    def rank(
        self,
        intent: StepIntent,
        candidates: List[Dict[str, Any]],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        query_fields = self._extract_fields(query)
        ranked: List[Dict[str, Any]] = []
        for candidate in candidates:
            scored = copy.deepcopy(candidate)
            scores = self._score_candidate(intent, candidate, query_fields)
            scored["rerank_score"] = scores["total"]
            scored["rerank_reasons"] = scores["reasons"]
            ranked.append(scored)
        return sorted(
            ranked,
            key=lambda item: (item.get("rerank_score", 0.0), item.get("score", 0.0)),
            reverse=True,
        )

    def is_structurally_compatible(
        self,
        intent: StepIntent,
        candidate: Dict[str, Any],
    ) -> bool:
        method_score, _ = self._method_score(intent.method, candidate.get("method", ""))
        object_score, _ = self._object_score(intent.object, candidate.get("object", ""))
        return method_score > 0.0 and object_score > 0.0

    def _score_candidate(
        self,
        intent: StepIntent,
        candidate: Dict[str, Any],
        query_fields: List[str],
    ) -> Dict[str, Any]:
        method_score, method_reason = self._method_score(intent.method, candidate.get("method", ""))
        object_score, object_reason = self._object_score(intent.object, candidate.get("object", ""))
        field_score, field_reason = self._field_score(query_fields, candidate)
        schema_score, schema_reason = self._schema_score(intent.method, candidate)
        rag_score = self._bounded_float(candidate.get("score", 0.0))

        total = (
            self.RAG_WEIGHT * rag_score
            + self.METHOD_WEIGHT * method_score
            + self.OBJECT_WEIGHT * object_score
            + self.FIELD_WEIGHT * field_score
            + self.SCHEMA_WEIGHT * schema_score
        )

        if method_score == 0.0:
            total -= 0.25
        if object_score == 0.0:
            total -= 0.25
        if query_fields and field_score == 0.0:
            total -= 0.10

        return {
            "total": round(max(total, 0.0), 6),
            "reasons": {
                "rag_score": rag_score,
                "method": method_reason,
                "object": object_reason,
                "fields": field_reason,
                "schema": schema_reason,
            },
        }

    def _method_score(self, expected: str, actual: str) -> tuple[float, str]:
        expected_norm = normalize_method(expected)
        actual_norm = normalize_method(actual)
        if expected_norm == actual_norm:
            return 1.0, "exact_match"
        for family in self.METHOD_FAMILIES:
            normalized = {normalize_method(item) for item in family}
            if expected_norm in normalized and actual_norm in normalized:
                return 0.6, "family_match"
        return 0.0, "mismatch"

    @staticmethod
    def _object_score(expected: str, actual: str) -> tuple[float, str]:
        expected_norm = RAGReranker._normalize_text(expected)
        actual_norm = RAGReranker._normalize_text(actual)
        if expected_norm and expected_norm == actual_norm:
            return 1.0, "exact_match"
        if expected_norm and actual_norm and (
            expected_norm in actual_norm or actual_norm in expected_norm
        ):
            return 0.5, "partial_match"
        expected_parts = set(expected_norm.split())
        actual_parts = set(actual_norm.split())
        if expected_parts and actual_parts:
            overlap = len(expected_parts.intersection(actual_parts)) / len(expected_parts)
            if overlap >= 0.6:
                return 0.35, "family_overlap"
        return 0.0, "mismatch"

    def _field_score(
        self,
        query_fields: List[str],
        candidate: Dict[str, Any],
    ) -> tuple[float, Dict[str, Any]]:
        candidate_fields = self._candidate_fields(candidate)
        if not query_fields:
            return 1.0, {"requested": [], "matched": [], "coverage": 1.0}

        requested_norm = {self._normalize_field(field): field for field in query_fields}
        candidate_norm = {self._normalize_field(field): field for field in candidate_fields}
        matched = [
            requested_norm[key]
            for key in requested_norm
            if key in candidate_norm
        ]
        coverage = len(matched) / len(requested_norm) if requested_norm else 1.0
        return coverage, {
            "requested": list(query_fields),
            "candidate_fields": sorted(candidate_fields),
            "matched": matched,
            "coverage": round(coverage, 3),
        }

    def _schema_score(self, expected_method: str, candidate: Dict[str, Any]) -> tuple[float, str]:
        method = normalize_method(expected_method)
        test_data = candidate.get("test_data") or {}
        if method == "Create":
            return (1.0, "create_section") if self._has_section(test_data, "create") else (0.0, "missing_create_section")
        if method == "Update":
            return (1.0, "update_section") if self._has_section(test_data, "update") else (0.0, "missing_update_section")
        if method == "Delete":
            return 1.0, "delete_no_parameter_section_required"
        if "Verify" in expected_method:
            return (1.0, "editor_section") if self._has_section(test_data, "editor") else (0.5, "no_editor_section")
        return 0.75, "schema_not_strictly_checked"

    @staticmethod
    def _has_section(test_data: Dict[str, Any], section: str) -> bool:
        value = test_data.get(section)
        return isinstance(value, dict) and bool(value)

    @classmethod
    def _candidate_fields(cls, candidate: Dict[str, Any]) -> set[str]:
        fields: set[str] = set()
        instruction = str(candidate.get("instruction", ""))
        fields.update(cls._extract_fields(instruction))
        test_data = candidate.get("test_data") or {}
        cls._collect_field_names(test_data, fields)
        return {field for field in fields if field}

    @classmethod
    def _collect_field_names(cls, value: Any, fields: set[str]) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if cls._looks_like_field_name(key):
                    fields.add(str(key))
                cls._collect_field_names(nested, fields)
        elif isinstance(value, list):
            for item in value:
                cls._collect_field_names(item, fields)

    @classmethod
    def _extract_fields(cls, text: str) -> List[str]:
        fields: List[str] = []
        for match in re.finditer(r"\bwith\s+(.+?)(?:\s+in\s+\w+|$)", text, flags=re.IGNORECASE):
            fields.extend(cls._split_field_phrase(match.group(1)))
        for match in re.finditer(r"\bwhere\s+(.+?)\s+have\s+", text, flags=re.IGNORECASE):
            fields.extend(cls._split_field_phrase(match.group(1)))
        for match in re.finditer(r"\bset\s+(.+?)\s+(?:to|=)\s+", text, flags=re.IGNORECASE):
            fields.extend(cls._split_field_phrase(match.group(1)))
        return cls._dedupe_preserve_order([field for field in fields if cls._looks_like_field_name(field)])

    @staticmethod
    def _split_field_phrase(phrase: str) -> List[str]:
        phrase = re.sub(r"\band\b", ",", phrase, flags=re.IGNORECASE)
        parts = []
        for raw in phrase.split(","):
            field = re.split(r"\s*(?:=| is | to )\s*", raw, maxsplit=1, flags=re.IGNORECASE)[0]
            field = field.strip(" .:;")
            if field:
                parts.append(field)
        return parts

    @staticmethod
    def _looks_like_field_name(value: str) -> bool:
        if not value or len(value) > 80:
            return False
        lowered = value.strip().lower()
        blocked = {
            "create",
            "update",
            "delete",
            "editor",
            "object",
            "type",
            "dataset",
            "custom",
            "id",
        }
        if lowered in blocked or lowered.startswith("fld_cstm"):
            return False
        return any(char.isalpha() for char in value)

    @staticmethod
    def _dedupe_preserve_order(values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            key = RAGReranker._normalize_field(value)
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @staticmethod
    def _normalize_field(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()

    @staticmethod
    def _bounded_float(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return min(max(number, 0.0), 1.0)


class RAGAgent(BaseAgent):
    """Attempts to retrieve a method/object-compatible template from RAG."""

    name = "RAGAgent"

    def __init__(
        self,
        runtime: Optional[Dict[str, Any]] = None,
        reranker: Optional[RAGReranker] = None,
    ):
        self.runtime = runtime
        self.reranker = reranker or RAGReranker()

    def run(self, state: WorkflowState) -> WorkflowState:
        state.active_template = None
        state.active_template_source = ""

        if not state.generation_config.get("use_rag", False):
            return self._trace_skip(state, "RAG disabled.")

        scaffolder = self._scaffolder(state)
        if scaffolder.rag is None:
            rag_index_dir = state.generation_config.get("rag_index_dir", "data/processed/rag_index")
            if not scaffolder.load_rag_engine(rag_index_dir):
                return self._trace_skip(state, "RAG index could not be loaded.")

        intent = self._active_intent(state)
        query = state.prompt if state.active_intent_index == 0 else f"{intent.method} {intent.object}"
        top_k = int(state.generation_config.get("rag_top_k", 10))
        try:
            results = scaffolder.rag.retrieve(query, top_k=top_k)
        except Exception as exc:
            return self._trace_skip(state, f"RAG retrieve failed: {exc}")

        compatible_results = [
            result
            for result in results
            if self.reranker.is_structurally_compatible(intent, result)
        ]

        selected = self.reranker.select(intent, compatible_results, query=query)
        if selected is not None:
            state.active_template = copy.deepcopy(selected)
            state.active_template_source = "rag"
            state.add_trace(
                self.name,
                "retrieve",
                query,
                f"Matched RAG template: {selected.get('instruction', '')}",
                {
                    "score": selected.get("score"),
                    "rerank_score": selected.get("rerank_score"),
                    "rerank_reasons": selected.get("rerank_reasons", {}),
                    "candidate_count": len(results),
                    "compatible_candidate_count": len(compatible_results),
                    "step_index": state.active_intent_index,
                    "contract": {
                        "outcome": "hit",
                        "reason": "compatible_template_found_by_reranker",
                        "template_source": "rag",
                        "next": "materialize",
                    },
                },
            )
            return state

        return self._trace_skip(state, f"No compatible RAG template for {query}.")

    def _scaffolder(self, state: WorkflowState) -> InteractiveScaffolder:
        scaffolder = self._runtime(state).get("scaffolder")
        if scaffolder is None:
            raise ValueError("Generation runtime missing scaffolder.")
        return scaffolder

    def _runtime(self, state: WorkflowState) -> Dict[str, Any]:
        return self.runtime if self.runtime is not None else state.runtime

    @staticmethod
    def _active_intent(state: WorkflowState) -> StepIntent:
        return state.plan[state.active_intent_index]

    def _trace_skip(self, state: WorkflowState, reason: str) -> WorkflowState:
        intent = self._active_intent(state)
        state.add_trace(
            self.name,
            "skip",
            f"{intent.method} {intent.object}",
            reason,
            {
                "step_index": state.active_intent_index,
                "contract": {
                    "outcome": "miss",
                    "reason": reason,
                    "template_source": None,
                    "next": "fine_tuned_model_or_fallback",
                },
            },
        )
        return state


class FineTunedModelAgent(BaseAgent):
    """Attempts to generate a step template with the local fine-tuned model."""

    name = "FineTunedModelAgent"

    def __init__(self, runtime: Optional[Dict[str, Any]] = None):
        self.runtime = runtime

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.active_template is not None:
            return self._trace_skip(state, "Template already supplied by previous agent.")

        if not state.generation_config.get("load_llm", False):
            return self._trace_skip(state, "Fine-tuned model disabled.")

        scaffolder = self._scaffolder(state)
        if scaffolder.llm_predictor is None and not self._load_predictor(state, scaffolder):
            return self._trace_skip(state, "Fine-tuned model could not be loaded.")

        intent = self._active_intent(state)
        instruction = (
            state.prompt
            if state.active_intent_index == 0 and state.prompt
            else f"{intent.method} {intent.object}"
        )
        try:
            predicted = scaffolder.llm_predictor.predict_step(instruction)
        except Exception as exc:
            return self._trace_skip(state, f"Prediction failed: {exc}")

        if predicted and isinstance(predicted, dict):
            predicted = copy.deepcopy(predicted)
            predicted["_llm_raw_template"] = copy.deepcopy(predicted)
            predicted["method"] = intent.method
            predicted["object"] = intent.object
            predicted["database"] = str(getattr(scaffolder, "database", "elektra")).lstrip(":")
            predicted["module"] = "Datamodel CRUD"
            predicted["command"] = "Execute Datamodel CRUD Testcommand"
            predicted["test_data"] = self._derive_test_data_from_llm(
                predicted["_llm_raw_template"],
                intent,
                scaffolder,
            )
            predicted["_llm_generated"] = True
            predicted["_llm_instruction"] = instruction
            state.active_template = predicted
            state.active_template_source = "fine_tuned_model"
            state.add_trace(
                self.name,
                "predict",
                instruction,
                "Generated template with fine-tuned model.",
                {
                    "step_index": state.active_intent_index,
                    "contract": {
                        "outcome": "generated",
                        "reason": "parseable_template",
                        "template_source": "fine_tuned_model",
                        "next": "materialize",
                    },
                },
            )
            return state

        preview = str(getattr(scaffolder.llm_predictor, "last_completion", ""))[:500]
        state.add_trace(
            self.name,
            "parse_failed",
            instruction,
            "Fine-tuned model returned no parseable JSON.",
            {
                "step_index": state.active_intent_index,
                "completion_preview": preview,
                "contract": {
                    "outcome": "parse_failed",
                    "reason": "no_parseable_json",
                    "template_source": None,
                    "next": "fallback",
                },
            },
        )
        return state

    def _scaffolder(self, state: WorkflowState) -> InteractiveScaffolder:
        scaffolder = self._runtime(state).get("scaffolder")
        if scaffolder is None:
            raise ValueError("Generation runtime missing scaffolder.")
        return scaffolder

    def _runtime(self, state: WorkflowState) -> Dict[str, Any]:
        return self.runtime if self.runtime is not None else state.runtime

    @staticmethod
    def _active_intent(state: WorkflowState) -> StepIntent:
        return state.plan[state.active_intent_index]

    def _load_predictor(self, state: WorkflowState, scaffolder: InteractiveScaffolder) -> bool:
        try:
            backend = state.generation_config.get("model_backend", "transformers")
            if backend == "llama_cpp_server":
                from src.inference.llama_cpp_predictor import LlamaCppServerPredictor

                scaffolder.llm_predictor = LlamaCppServerPredictor(
                    server_url=state.generation_config.get("llama_server_url", "http://127.0.0.1:8080"),
                    max_tokens=state.generation_config.get("max_tokens", 512),
                    temperature=state.generation_config.get("temperature", 0.0),
                    top_p=state.generation_config.get("top_p", 1.0),
                )
                state.add_trace(
                    self.name,
                    "load",
                    "llama.cpp server",
                    "Configured LlamaCppServerPredictor.",
                    {
                        "server_url": state.generation_config.get("llama_server_url", "http://127.0.0.1:8080"),
                        "contract": {
                            "outcome": "available",
                            "reason": "llama_cpp_server_configured",
                            "next": "predict",
                        },
                    },
                )
                return True

            from src.inference.step_llm_predictor import StepLevelPredictor

            scaffolder.llm_predictor = StepLevelPredictor(
                model_dir=state.generation_config.get("model_dir", "models/step-level-model-865"),
                verbose=False,
                quantization=state.generation_config.get("model_quantization"),
            )
            state.add_trace(
                self.name,
                "load",
                "local fine-tuned model",
                "Loaded StepLevelPredictor.",
                {
                    "contract": {
                        "outcome": "available",
                        "reason": "model_loaded",
                        "next": "predict",
                    }
                },
            )
            return True
        except Exception as exc:
            state.add_trace(
                self.name,
                "load_failed",
                "local fine-tuned model",
                f"Could not load StepLevelPredictor: {exc}",
                {
                    "contract": {
                        "outcome": "unavailable",
                        "reason": str(exc),
                        "next": "fallback",
                    }
                },
            )
            scaffolder.llm_predictor = None
            return False

    @staticmethod
    def _derive_test_data_from_llm(
        raw_template: Dict[str, Any],
        intent: StepIntent,
        scaffolder: InteractiveScaffolder,
    ) -> Dict[str, Any]:
        test_data = raw_template.get("test_data")
        method_key = intent.method.lower()
        if method_key == "open":
            method_key = "editor"

        if isinstance(test_data, dict) and method_key in test_data:
            method_block = test_data.get(method_key)
            if intent.method in {"Create", "Update"} and isinstance(method_block, dict):
                if any(str(key).startswith("FLD_CSTM") for key in method_block):
                    return copy.deepcopy(test_data)
            elif intent.method == "Delete" and isinstance(method_block, dict):
                return copy.deepcopy(test_data)
            elif intent.method in {"Open", "Switch", "Run", "Verify"}:
                return copy.deepcopy(test_data)

        return scaffolder._generate_test_data_body(
            intent.object,
            intent.method,
            "LLM_PENDING_ID",
        )

    def _trace_skip(self, state: WorkflowState, reason: str) -> WorkflowState:
        intent = self._active_intent(state)
        state.add_trace(
            self.name,
            "skip",
            f"{intent.method} {intent.object}",
            reason,
            {
                "step_index": state.active_intent_index,
                "contract": {
                    "outcome": "unavailable",
                    "reason": reason,
                    "template_source": None,
                    "next": "fallback",
                },
            },
        )
        return state


class FallbackAgent(BaseAgent):
    """Marks the active step for deterministic heuristic generation."""

    name = "FallbackAgent"

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.active_template is None:
            state.active_template_source = "heuristic"
            intent = state.plan[state.active_intent_index]
            state.add_trace(
                self.name,
                "fallback",
                f"{intent.method} {intent.object}",
                "Using deterministic scaffolder fallback.",
                {
                    "step_index": state.active_intent_index,
                    "contract": {
                        "outcome": "selected",
                        "reason": "no_external_template_available",
                        "template_source": "heuristic",
                        "next": "materialize",
                    },
                },
            )
        return state


class StepMaterializerAgent(BaseAgent):
    """Writes the active step into the scaffolder workflow."""

    name = "StepMaterializerAgent"

    def __init__(self, runtime: Optional[Dict[str, Any]] = None):
        self.runtime = runtime
        self.normalizer = StepTemplateNormalizer()

    def run(self, state: WorkflowState) -> WorkflowState:
        runtime = self._runtime(state)
        scaffolder = runtime.get("scaffolder")
        if scaffolder is None:
            raise ValueError("Generation runtime missing scaffolder.")

        intent = state.plan[state.active_intent_index]
        template = state.active_template
        source = state.active_template_source or "heuristic"

        if state.active_intent_index == 0:
            if template:
                step = self._materialize_first_from_template(scaffolder, template, intent)
            else:
                step = scaffolder.parse_and_create_step_one(
                    f"{intent.method} {intent.object}",
                    use_rag=False,
                )
        else:
            previous_step = runtime.get("previous_step")
            recommendation = {
                "type": intent.source,
                "object": intent.object,
                "method": intent.method,
                "description": intent.reason,
            }
            step = scaffolder.build_cascade_step(
                recommendation,
                previous_step,
                template_match=template,
                allow_template_lookup=False,
            )

        contract_repairs = self._ensure_validator_compatible_step(
            step,
            expected_index=state.active_intent_index,
            intent=intent,
            source=source,
        )
        runtime["previous_step"] = step
        state.active_intent_index += 1
        state.active_template = None
        state.active_template_source = ""
        state.generation_complete = state.active_intent_index >= len(state.plan)
        if state.generation_complete:
            state.workflow = json.loads(scaffolder.get_full_workflow_json())
            state.status = "generated"

        state.add_trace(
            self.name,
            "materialize",
            f"{intent.method} {intent.object}",
            f"Materialized step {step.get('step_index')} from {source}.",
            {
                "step_index": step.get("step_index"),
                "source": source,
                "contract": {
                    "outcome": "validator_compatible_step",
                    "reason": "materialized_and_normalized",
                    "repairs": contract_repairs,
                    "required_keys": sorted(REQUIRED_STEP_KEYS),
                    "next": "continue_or_validate",
                },
            },
        )
        return state

    def _runtime(self, state: WorkflowState) -> Dict[str, Any]:
        return self.runtime if self.runtime is not None else state.runtime

    def _materialize_first_from_template(
        self,
        scaffolder: InteractiveScaffolder,
        template: Dict[str, Any],
        intent: StepIntent,
    ) -> Dict[str, Any]:
        method = normalize_method(intent.method)
        obj = intent.object
        generated_id = str(random.randint(86393281400000, 86393281499999))
        if method == "Create":
            scaffolder.last_created_ids[obj] = generated_id

        step_data = self.normalizer.normalize(
            template,
            method,
            obj,
            scaffolder,
            object_id=generated_id if method == "Create" else "Passed",
        )
        step_data["step_index"] = 0
        step_data["_source"] = "template"
        if not str(step_data["database"]).startswith(":") and step_data["database"]:
            step_data["database"] = f":{step_data['database']}"
        scaffolder.steps.append(step_data)
        return step_data

    @staticmethod
    def _ensure_validator_compatible_step(
        step: Dict[str, Any],
        expected_index: int,
        intent: StepIntent,
        source: str,
    ) -> List[str]:
        repairs: List[str] = []
        if not isinstance(step, dict):
            return ["step_not_object_unrepairable"]

        if step.get("step_index") != expected_index:
            step["step_index"] = expected_index
            repairs.append("step_index")

        if not step.get("database"):
            step["database"] = ":elektra"
            repairs.append("database")

        method = normalize_method(str(step.get("method") or intent.method))
        if method not in VALID_METHODS:
            method = normalize_method(intent.method)
            repairs.append("method")
        step["method"] = method

        if not str(step.get("object", "")).strip():
            step["object"] = intent.object
            repairs.append("object")

        if not str(step.get("module", "")).strip():
            step["module"] = "Datamodel CRUD" if method in {"Create", "Update", "Delete"} else "Object Editor"
            repairs.append("module")

        if not str(step.get("command", "")).strip():
            step["command"] = (
                "Execute Datamodel CRUD Testcommand"
                if method in {"Create", "Update", "Delete"}
                else f"{method} {step.get('object', intent.object)}"
            )
            repairs.append("command")

        if "object_id" not in step or RepairAgent._is_blank(step.get("object_id")):
            step["object_id"] = (
                str(random.randint(86393281400000, 86393281499999))
                if method == "Create"
                else "Passed"
            )
            repairs.append("object_id")

        if method == "Create" and step.get("object_id") == "Passed":
            step["object_id"] = str(random.randint(86393281400000, 86393281499999))
            repairs.append("create_object_id")

        if not isinstance(step.get("test_data"), dict):
            step["test_data"] = {}
            repairs.append("test_data")

        step["_materializer_source"] = source
        return repairs


class ValidatorAgent(BaseAgent):
    """Checks schema, indices, IDs, and basic GIS workflow consistency."""

    name = "ValidatorAgent"

    def run(self, state: WorkflowState) -> WorkflowState:
        findings: List[Finding] = []
        workflow = state.workflow

        if not isinstance(workflow, dict):
            findings.append(Finding("error", "workflow_not_object", "Workflow is not a dict."))
            state.findings = findings
            state.status = "invalid"
            state.validation_route = classify_validation_failure(findings)
            state.add_trace(
                self.name,
                "validate",
                "Workflow root.",
                "Workflow is not an object.",
                {"validation_route": state.validation_route},
            )
            return state

        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            findings.append(Finding("error", "missing_steps", "Workflow has no steps list."))
            state.findings = findings
            state.status = "invalid"
            state.validation_route = classify_validation_failure(findings)
            state.add_trace(
                self.name,
                "validate",
                "Workflow steps.",
                "Workflow has no usable steps list.",
                {"validation_route": state.validation_route},
            )
            return state

        total_steps = workflow.get("total_steps")
        if total_steps != len(steps):
            findings.append(
                Finding(
                    "error",
                    "total_steps_mismatch",
                    f"total_steps={total_steps} but steps length={len(steps)}.",
                )
            )

        created_ids = set()
        for expected_index, step in enumerate(steps):
            findings.extend(self._validate_step(step, expected_index))
            if not isinstance(step, dict):
                continue
            method = step.get("method")
            object_id = step.get("object_id")
            if method == "Create" and object_id in created_ids:
                findings.append(
                    Finding(
                        "warning",
                        "duplicate_create_id",
                        f"Create ID {object_id} was already used.",
                        expected_index,
                    )
                )
            if method == "Create" and object_id:
                created_ids.add(object_id)

        state.findings = findings
        state.status = "invalid" if any(f.is_error for f in findings) else "validated"
        state.validation_route = classify_validation_failure(findings)
        state.add_trace(
            self.name,
            "validate",
            f"Workflow with {len(steps)} steps.",
            f"{len(findings)} findings, {len([f for f in findings if f.is_error])} errors.",
            {
                "validation_route": state.validation_route,
                "contract": {
                    "outcome": state.validation_route,
                    "reason": "classified_validation_findings",
                    "next": state.validation_route,
                },
            },
        )
        return state

    @staticmethod
    def _validate_step(step: Any, expected_index: int) -> List[Finding]:
        findings: List[Finding] = []
        if not isinstance(step, dict):
            return [
                Finding(
                    "error",
                    "step_not_object",
                    "Step is not a dict.",
                    expected_index,
                )
            ]

        missing = REQUIRED_STEP_KEYS.difference(step.keys())
        for key in sorted(missing):
            findings.append(
                Finding("error", "missing_step_key", f"Step is missing key: {key}.", expected_index)
            )

        if step.get("step_index") != expected_index:
            findings.append(
                Finding(
                    "error",
                    "step_index_mismatch",
                    f"Expected step_index {expected_index}, got {step.get('step_index')}.",
                    expected_index,
                )
            )

        method = step.get("method")
        if method not in VALID_METHODS:
            findings.append(
                Finding("error", "unknown_method", f"Unknown method: {method}.", expected_index)
            )

        if not str(step.get("object", "")).strip():
            findings.append(Finding("error", "missing_object", "Step object is empty.", expected_index))

        if method == "Create" and step.get("object_id") in {"", None, "Passed"}:
            findings.append(
                Finding("error", "missing_create_id", "Create step needs a concrete object_id.", expected_index)
            )

        if not isinstance(step.get("test_data"), dict):
            findings.append(
                Finding("error", "test_data_not_object", "test_data must be a dict.", expected_index)
            )

        return findings


class RepairAgent(BaseAgent):
    """Applies deterministic repairs for recoverable validation errors."""

    name = "RepairAgent"

    def run(self, state: WorkflowState) -> WorkflowState:
        workflow = copy.deepcopy(state.workflow)
        steps = workflow.get("steps", [])
        repairs: List[str] = []

        if isinstance(steps, list):
            workflow["total_steps"] = len(steps)
            repairs.append("Normalized workflow.total_steps.")

            for index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                if step.get("step_index") != index:
                    step["step_index"] = index
                    repairs.append(f"Fixed step_index for step {index}.")
                self._fill_step_defaults(step, index, repairs)

        state.workflow = workflow
        state.repairs.extend(repairs)
        state.status = "repaired"
        state.add_trace(
            self.name,
            "repair",
            f"{len(state.findings)} validation findings.",
            f"Applied {len(repairs)} deterministic repairs.",
            {"repairs": repairs},
        )
        return state

    @staticmethod
    def _fill_step_defaults(step: Dict[str, Any], index: int, repairs: List[str]) -> None:
        defaults = {
            "database": ":elektra",
            "object": "E MS Installatie FP",
            "module": "Datamodel CRUD",
            "method": "Create",
            "command": "Execute Datamodel CRUD Testcommand",
            "test_data": {},
        }
        for key, value in defaults.items():
            if key not in step or RepairAgent._is_blank(step.get(key)):
                step[key] = copy.deepcopy(value)
                repairs.append(f"Filled missing {key} for step {index}.")

        if "object_id" not in step or RepairAgent._is_blank(step.get("object_id")):
            step["object_id"] = str(random.randint(86393281400000, 86393281499999))
            repairs.append(f"Filled missing object_id for step {index}.")

        if step.get("method") == "Create" and step.get("object_id") == "Passed":
            step["object_id"] = str(random.randint(86393281400000, 86393281499999))
            repairs.append(f"Generated create object_id for step {index}.")

        if not isinstance(step.get("test_data"), dict):
            step["test_data"] = {}
            repairs.append(f"Reset test_data for step {index}.")

    @staticmethod
    def _is_blank(value: Any) -> bool:
        return value is None or value == ""


class ReviewerAgent(BaseAgent):
    """Summarizes the final result and assigns a simple confidence score."""

    name = "ReviewerAgent"

    def run(self, state: WorkflowState) -> WorkflowState:
        error_count = len([finding for finding in state.findings if finding.is_error])
        warning_count = len([finding for finding in state.findings if not finding.is_error])
        step_count = len(state.workflow.get("steps", [])) if isinstance(state.workflow, dict) else 0

        if state.status == "needs_human_review":
            state.confidence = max(0.0, 0.45 - 0.08 * error_count)
        elif error_count:
            state.status = "failed"
            state.confidence = max(0.0, 0.55 - 0.1 * error_count)
        else:
            state.status = "ready"
            state.confidence = max(0.0, 0.95 - 0.03 * warning_count)

        state.add_trace(
            self.name,
            "review",
            f"{error_count} errors, {warning_count} warnings.",
            f"status={state.status}, confidence={state.confidence:.2f}, steps={step_count}.",
        )
        return state
