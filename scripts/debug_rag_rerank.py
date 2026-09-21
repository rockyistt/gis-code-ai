#!/usr/bin/env python3
"""Inspect RAG top-k retrieval and rule-based reranking for one query."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents import ContextManagerAgent, RAGReranker, StepIntent, WorkflowState  # noqa: E402
from src.inference.rag_utils import StepRAG  # noqa: E402


TEMPLATE_KEYS = (
    "instruction",
    "module",
    "method",
    "object",
    "database",
    "command",
    "object_id",
    "test_data",
)


def infer_intent(prompt: str, method: str | None, obj: str | None) -> StepIntent:
    if method and obj:
        return StepIntent(method=method, object=obj, source="cli")

    state = ContextManagerAgent().run(WorkflowState(prompt=prompt))
    if state.context_intents:
        return state.context_intents[0]

    raise SystemExit(
        "Could not infer method/object from prompt. "
        "Pass --method and --object explicitly."
    )


def print_candidate(
    rank: int,
    candidate: Dict[str, Any],
    show_reasons: bool = False,
    show_json: bool = False,
) -> None:
    print(
        f"{rank:>2}. "
        f"rag={candidate.get('score', 0.0):.4f} "
        f"dense={candidate.get('score_dense', 0.0):.4f} "
        f"kw={candidate.get('score_keyword', 0.0):.4f} "
        f"rerank={candidate.get('rerank_score', 0.0):.4f} "
        f"[{candidate.get('method', '')}] {candidate.get('object', '')}"
    )
    print(f"    {candidate.get('instruction', '')}")
    if show_reasons and candidate.get("rerank_reasons"):
        print("    reasons:")
        print(
            indent(
                json.dumps(candidate["rerank_reasons"], indent=2, ensure_ascii=False),
                "      ",
            )
        )
    if show_json:
        print("    raw template JSON:")
        print(indent(format_template_json(candidate), "      "))


def format_template_json(candidate: Dict[str, Any]) -> str:
    template = {
        key: candidate[key]
        for key in TEMPLATE_KEYS
        if key in candidate
    }
    return json.dumps(template, indent=2, ensure_ascii=False)


def indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show RAG retrieval candidates before and after rule-based reranking."
    )
    parser.add_argument("prompt", nargs="+", help="User GIS instruction.")
    parser.add_argument("--method", default=None, help="Override inferred method.")
    parser.add_argument("--object", default=None, help="Override inferred object.")
    parser.add_argument("--rag-index-dir", default="data/processed/rag_index")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--show-reasons",
        action="store_true",
        help="Print detailed rerank reasons for every reranked candidate.",
    )
    parser.add_argument(
        "--show-json",
        choices=["selected", "all", "none"],
        default="selected",
        help=(
            "Print raw JSON template for the selected candidate, every candidate, "
            "or none. Default: selected."
        ),
    )
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    intent = infer_intent(prompt, args.method, args.object)

    print("=" * 88)
    print(f"Prompt: {prompt}")
    print(f"Intent: {intent.method} {intent.object}")
    print("=" * 88)

    rag = StepRAG()
    rag.load(args.rag_index_dir)
    results = rag.retrieve(prompt, top_k=args.top_k)

    print("\nRAG top-k before reranking")
    print("-" * 88)
    for idx, candidate in enumerate(results, start=1):
        print_candidate(idx, candidate, show_json=args.show_json == "all")

    reranker = RAGReranker()
    structurally_compatible = [
        candidate
        for candidate in results
        if reranker.is_structurally_compatible(intent, candidate)
    ]
    ranked = reranker.rank(intent, structurally_compatible, query=prompt)

    print("\nStructurally compatible candidates")
    print("-" * 88)
    if not structurally_compatible:
        print("No method/object-compatible candidates found in top-k.")
    else:
        for idx, candidate in enumerate(structurally_compatible, start=1):
            print_candidate(idx, candidate, show_json=args.show_json == "all")

    print("\nAfter rule-based reranking")
    print("-" * 88)
    if not ranked:
        print("No candidate selected.")
    else:
        for idx, candidate in enumerate(ranked, start=1):
            print_candidate(
                idx,
                candidate,
                show_reasons=args.show_reasons,
                show_json=args.show_json == "all",
            )

        selected = ranked[0]
        print("\nSelected template")
        print("-" * 88)
        print_candidate(
            1,
            selected,
            show_reasons=True,
            show_json=args.show_json in {"selected", "all"},
        )


if __name__ == "__main__":
    main()
