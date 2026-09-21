#!/usr/bin/env python3
"""Compare raw RAG retrieval pools with rule-based reranking at multiple top-K sizes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents import RAGReranker, StepIntent  # noqa: E402
from src.inference.rag_utils import StepRAG  # noqa: E402


def compatible(expected: Dict[str, Any], retrieved: Optional[Dict[str, Any]]) -> bool:
    if not retrieved:
        return False
    return (
        norm(expected.get("method")) == norm(retrieved.get("method"))
        and norm(expected.get("object")) == norm(retrieved.get("object"))
    )


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def make_query(item: Dict[str, Any], mode: str) -> str:
    if mode == "instruction":
        return str(item.get("instruction", ""))
    if mode == "intent":
        return f"{item.get('method', '')} {item.get('object', '')}".strip()
    raise ValueError(f"Unsupported query mode: {mode}")


def is_parameterized(item: Dict[str, Any]) -> bool:
    instruction = str(item.get("instruction", ""))
    return bool(
        RAGReranker._extract_fields(instruction)
        or " of station " in instruction
        or " with id " in instruction
        or " hierarchy " in instruction and " indexed " in instruction
    )


def evaluate_case(
    rag: StepRAG,
    reranker: RAGReranker,
    expected: Dict[str, Any],
    query: str,
    top_ks: List[int],
    exclude_self: bool,
) -> Dict[str, Any]:
    max_k = max(top_ks)
    retrieve_k = max_k + 1 if exclude_self else max_k
    results = rag.retrieve(query, top_k=retrieve_k)
    if exclude_self:
        expected_instruction = expected.get("instruction", "")
        results = [
            result for result in results
            if result.get("instruction") != expected_instruction
        ][:max_k]

    baseline = results[0] if results else None
    pool_hits = {
        f"candidate_pool_compatible@{k}": any(
            compatible(expected, result) for result in results[:k]
        )
        for k in top_ks
    }
    intent = StepIntent(
        method=str(expected.get("method", "")),
        object=str(expected.get("object", "")),
        source="evaluation",
    )
    reranked_by_k: Dict[str, bool] = {}
    selected_by_k: Dict[str, Optional[Dict[str, Any]]] = {}
    compatible_counts_by_k: Dict[str, int] = {}
    for k in top_ks:
        pool = results[:k]
        structurally_compatible = [
            result for result in pool
            if reranker.is_structurally_compatible(intent, result)
        ]
        reranked = reranker.rank(intent, structurally_compatible, query=query)
        selected = reranked[0] if reranked else None
        reranked_by_k[f"reranked_compatible@1_from_top{k}"] = compatible(expected, selected)
        selected_by_k[f"top{k}"] = summarize_candidate(selected)
        compatible_counts_by_k[f"top{k}"] = len(structurally_compatible)

    max_key = f"top{max_k}"
    selected = selected_by_k.get(max_key)

    return {
        "query": query,
        "expected_method": expected.get("method"),
        "expected_object": expected.get("object"),
        "expected_instruction": expected.get("instruction"),
        "baseline": summarize_candidate(baseline),
        "reranked": selected,
        "baseline_compatible": compatible(expected, baseline),
        "reranked_compatible": reranked_by_k[f"reranked_compatible@1_from_top{max_k}"],
        "candidate_pool_hits": pool_hits,
        "reranked_by_k": reranked_by_k,
        "selected_by_k": selected_by_k,
        "compatible_candidate_count_by_k": compatible_counts_by_k,
        "retrieved_count": len(results),
        "rerank_reasons": selected.get("rerank_reasons", {}) if selected else {},
    }


def summarize_candidate(candidate: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidate:
        return None
    return {
        "score": candidate.get("score"),
        "score_dense": candidate.get("score_dense"),
        "score_keyword": candidate.get("score_keyword"),
        "rerank_score": candidate.get("rerank_score"),
        "method": candidate.get("method"),
        "object": candidate.get("object"),
        "instruction": candidate.get("instruction"),
    }


def summarize(cases: List[Dict[str, Any]], top_ks: List[int]) -> Dict[str, Any]:
    total = len(cases)
    baseline_hits = sum(1 for case in cases if case["baseline_compatible"])
    pool_hit_counts = {
        f"candidate_pool_compatible@{k}": sum(
            1
            for case in cases
            if case["candidate_pool_hits"].get(f"candidate_pool_compatible@{k}", False)
        )
        for k in top_ks
    }
    rerank_hit_counts = {
        f"reranked_compatible@1_from_top{k}": sum(
            1
            for case in cases
            if case["reranked_by_k"].get(f"reranked_compatible@1_from_top{k}", False)
        )
        for k in top_ks
    }
    rerank_selected_counts = {
        f"top{k}": sum(
            1
            for case in cases
            if case["selected_by_k"].get(f"top{k}") is not None
        )
        for k in top_ks
    }
    pool_hit_rates = {
        key: rate(value, total)
        for key, value in pool_hit_counts.items()
    }
    rerank_hit_rates = {
        key: rate(value, total)
        for key, value in rerank_hit_counts.items()
    }
    oracle_gaps = {
        f"oracle_gap@{k}": pool_hit_rates[f"candidate_pool_compatible@{k}"]
        - rerank_hit_rates[f"reranked_compatible@1_from_top{k}"]
        for k in top_ks
    }
    absolute_improvements = {
        f"absolute_improvement@{k}": rate(
            rerank_hit_counts[f"reranked_compatible@1_from_top{k}"] - baseline_hits,
            total,
        )
        for k in top_ks
    }
    relative_improvements = {
        f"relative_improvement@{k}": (
            (
                rerank_hit_counts[f"reranked_compatible@1_from_top{k}"]
                - baseline_hits
            )
            / baseline_hits
            if baseline_hits else None
        )
        for k in top_ks
    }
    max_k = max(top_ks)
    max_rerank_key = f"reranked_compatible@1_from_top{max_k}"
    improvements = [
        case for case in cases
        if not case["baseline_compatible"]
        and case["reranked_by_k"].get(max_rerank_key, False)
    ]
    regressions = [
        case for case in cases
        if case["baseline_compatible"]
        and not case["reranked_by_k"].get(max_rerank_key, False)
    ]
    unchanged_good = [
        case for case in cases
        if case["baseline_compatible"]
        and case["reranked_by_k"].get(max_rerank_key, False)
    ]

    return {
        "total": total,
        "baseline_compatible@1": rate(baseline_hits, total),
        "reranked_compatible@1_by_pool": rerank_hit_rates,
        "candidate_pool_compatible": pool_hit_rates,
        "oracle_gap": oracle_gaps,
        "absolute_improvement": absolute_improvements,
        "relative_improvement": relative_improvements,
        "rerank_selection_rate_by_pool": {
            key: rate(value, total)
            for key, value in rerank_selected_counts.items()
        },
        "counts": {
            "baseline_hits": baseline_hits,
            "rerank_hits_by_pool": rerank_hit_counts,
            "improvements": len(improvements),
            "regressions": len(regressions),
            "unchanged_good": len(unchanged_good),
            "rerank_selected_by_pool": rerank_selected_counts,
            "candidate_pool_hits": pool_hit_counts,
        },
        "examples": {
            "improvements": improvements[:10],
            "regressions": regressions[:10],
        },
    }


def rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def parse_top_ks(raw: str) -> List[int]:
    values = sorted({int(part.strip()) for part in raw.split(",") if part.strip()})
    if not values:
        raise argparse.ArgumentTypeError("At least one top-K value is required.")
    if values[0] < 1:
        raise argparse.ArgumentTypeError("top-K values must be positive integers.")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate whether rule-based reranking improves RAG template selection."
    )
    parser.add_argument("--rag-index-dir", default="data/processed/rag_index")
    parser.add_argument("--query-mode", choices=["instruction", "intent"], default="intent")
    parser.add_argument(
        "--top-ks",
        type=parse_top_ks,
        default=parse_top_ks("1,3,5,10"),
        help="Comma-separated retrieval pool sizes, e.g. 1,3,5,10.",
    )
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--exclude-self", action="store_true")
    parser.add_argument("--only-parameterized", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    rag = StepRAG()
    rag.load(args.rag_index_dir)
    reranker = RAGReranker()

    metadata = list(rag.metadata)
    if args.only_parameterized:
        metadata = [item for item in metadata if is_parameterized(item)]
    if args.sample_limit:
        metadata = metadata[: args.sample_limit]

    cases = [
        evaluate_case(
            rag=rag,
            reranker=reranker,
            expected=item,
            query=make_query(item, args.query_mode),
            top_ks=args.top_ks,
            exclude_self=args.exclude_self,
        )
        for item in metadata
    ]
    report = {
        "config": {
            "query_mode": args.query_mode,
            "top_ks": args.top_ks,
            "exclude_self": args.exclude_self,
            "only_parameterized": args.only_parameterized,
            "sample_limit": args.sample_limit,
        },
        "summary": summarize(cases, args.top_ks),
        "cases": cases,
    }

    print("RAG reranker evaluation")
    print("=" * 80)
    for key, value in report["config"].items():
        print(f"{key}: {value}")
    print("-" * 80)
    summary = report["summary"]
    print(f"cases: {summary['total']}")
    print(
        "baseline compatible@1: "
        f"{summary['baseline_compatible@1']:.3f} "
        f"({summary['counts']['baseline_hits']}/{summary['total']})"
    )
    for k in args.top_ks:
        pool_key = f"candidate_pool_compatible@{k}"
        rerank_key = f"reranked_compatible@1_from_top{k}"
        gap_key = f"oracle_gap@{k}"
        improvement_key = f"absolute_improvement@{k}"
        relative_key = f"relative_improvement@{k}"
        selection_key = f"top{k}"
        print(
            f"{pool_key}: "
            f"{summary['candidate_pool_compatible'][pool_key]:.3f} "
            f"({summary['counts']['candidate_pool_hits'][pool_key]}/{summary['total']})"
        )
        print(
            f"{rerank_key}: "
            f"{summary['reranked_compatible@1_by_pool'][rerank_key]:.3f} "
            f"({summary['counts']['rerank_hits_by_pool'][rerank_key]}/{summary['total']})"
        )
        print(f"{gap_key}: {summary['oracle_gap'][gap_key]:.3f}")
        print(f"{improvement_key}: {summary['absolute_improvement'][improvement_key]:.3f}")
        relative = summary["relative_improvement"][relative_key]
        relative_text = f"{relative:.3f}" if relative is not None else "n/a"
        print(f"{relative_key}: {relative_text}")
        print(
            f"rerank_selection_rate@{k}: "
            f"{summary['rerank_selection_rate_by_pool'][selection_key]:.3f}"
        )
        print("-" * 40)
    print(f"improvements: {summary['counts']['improvements']}")
    print(f"regressions: {summary['counts']['regressions']}")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"report saved: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
