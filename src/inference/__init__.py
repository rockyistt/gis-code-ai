"""Inference helpers for RAG, fine-tuned models, and local GGUF serving."""

from __future__ import annotations

__all__ = ["HybridInferencer", "StepRAG", "load_rag"]
__version__ = "1.0.0"


def __getattr__(name: str):
    if name == "HybridInferencer":
        from .hybrid_inference import HybridInferencer

        return HybridInferencer
    if name in {"StepRAG", "load_rag"}:
        from .rag_utils import StepRAG, load_rag

        return {"StepRAG": StepRAG, "load_rag": load_rag}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
