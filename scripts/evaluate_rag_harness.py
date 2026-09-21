#!/usr/bin/env python3
"""Evaluate step-level RAG retrieval quality for GIS workflow templates."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.rag_utils import StepRAG  # noqa: E402


def compatible(expected: Dict[str, Any], retrieved: Dict[str, Any]) -> bool:
    return (
        str(expected.get("method", "")).strip().lower()
        == str(retrieved.get("method", "")).strip().lower()
        and str(expected.get("object", "")).strip().lower()
        == str(retrieved.get("object", "")).strip().lower()
    )


def evaluate(rag: StepRAG, sample_limit: int | None, top_ks: Iterable[int]) -> Dict[str, Any]:
    metadata = list(rag.metadata)
    if sample_limit:
        metadata = metadata[:sample_limit]

    top_ks = sorted(set(top_ks))
    max_k = max(top_ks)
    metrics = {
        f"self_recall@{k}": 0 for k in top_ks
    } | {
        f"compatible_hit@{k}": 0 for k in top_ks
    } | {
        f"non_self_compatible_hit@{k}": 0 for k in top_ks
    }
    cases: List[Dict[str, Any]] = []
    queries = [item.get("instruction", "") for item in metadata]
    model = rag._get_model()
    query_vectors = np.array(
        model.encode(queries, batch_size=64, normalize_embeddings=True),
        dtype=np.float32,
    )
    dense_scores = query_vectors @ rag.embeddings.T

    for idx, expected in enumerate(metadata):
        query = expected.get("instruction", "")
        kw_scores = np.array(
            [
                rag._keyword_overlap_score(query.lower(), meta.get("keyword_weights", {}))
                for meta in rag.metadata
            ],
            dtype=np.float32,
        )
        hybrid_scores = rag.alpha * dense_scores[idx] + (1.0 - rag.alpha) * kw_scores
        top_n = min(max_k + 1, len(hybrid_scores))
        top_indices = np.argpartition(hybrid_scores, -top_n)[-top_n:]
        top_indices = top_indices[np.argsort(hybrid_scores[top_indices])[::-1]]
        results = []
        for result_idx in top_indices:
            result = rag.metadata[int(result_idx)].copy()
            result["score"] = float(hybrid_scores[int(result_idx)])
            result["score_dense"] = float(dense_scores[idx][int(result_idx)])
            result["score_keyword"] = float(kw_scores[int(result_idx)])
            results.append(result)
        expected_instruction = expected.get("instruction", "")

        for k in top_ks:
            top = results[:k]
            non_self_top = [
                result for result in results if result.get("instruction") != expected_instruction
            ][:k]

            if any(result.get("instruction") == expected_instruction for result in top):
                metrics[f"self_recall@{k}"] += 1
            if any(compatible(expected, result) for result in top):
                metrics[f"compatible_hit@{k}"] += 1
            if any(compatible(expected, result) for result in non_self_top):
                metrics[f"non_self_compatible_hit@{k}"] += 1

        cases.append(
            {
                "case_index": idx,
                "query": query,
                "expected_method": expected.get("method"),
                "expected_object": expected.get("object"),
                "top_result": {
                    "score": results[0].get("score") if results else None,
                    "method": results[0].get("method") if results else None,
                    "object": results[0].get("object") if results else None,
                    "instruction": results[0].get("instruction") if results else None,
                },
            }
        )

    total = len(metadata)
    rates = {
        key: (value / total if total else 0.0)
        for key, value in metrics.items()
    }
    return {
        "total": total,
        "top_ks": top_ks,
        "counts": metrics,
        "rates": rates,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality.")
    parser.add_argument("--rag-index-dir", default="data/processed/rag_index")
    parser.add_argument("--sample-limit", type=int, default=None)
    parser.add_argument("--top-k", default="1,3,5")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    rag = StepRAG()
    rag.load(args.rag_index_dir)
    top_ks = [int(part) for part in args.top_k.split(",") if part.strip()]
    report = evaluate(rag, args.sample_limit, top_ks)

    print("RAG evaluation harness")
    print("=" * 72)
    print(f"cases: {report['total']}")
    for key, value in report["rates"].items():
        print(f"{key}: {value:.3f} ({report['counts'][key]}/{report['total']})")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"report saved: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
