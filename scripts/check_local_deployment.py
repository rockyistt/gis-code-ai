#!/usr/bin/env python3
"""Local deployment preflight for the GIS model and agent loop."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def status(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def check_file(path: Path, label: str) -> Tuple[bool, str]:
    return path.exists(), f"{status(path.exists())}: {label} -> {path}"


def check_python() -> List[Tuple[bool, str]]:
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 9
    return [
        (
            ok,
            f"{status(ok)}: Python {version.major}.{version.minor}.{version.micro} on {platform.system()}",
        )
    ]


def check_model(model_dir: Path) -> List[Tuple[bool, str]]:
    checks = []
    checks.append((model_dir.exists(), f"{status(model_dir.exists())}: model directory -> {model_dir}"))

    full_model = (model_dir / "model.safetensors").exists() or (model_dir / "pytorch_model.bin").exists()
    lora_bin = (model_dir / "adapter_model.bin").exists() or (model_dir / "adapter_model.safetensors").exists()
    lora = (model_dir / "adapter_config.json").exists() and lora_bin
    tokenizer = any(
        (model_dir / name).exists()
        for name in ("tokenizer.json", "tokenizer.model", "tokenizer_config.json")
    )

    checks.append((full_model or lora, f"{status(full_model or lora)}: model weights or LoRA adapter"))
    checks.append((tokenizer, f"{status(tokenizer)}: tokenizer artifacts"))
    training_info = model_dir / "training_info.json"
    training_message = (
        f"OK: optional training metadata -> {training_info}"
        if training_info.exists()
        else f"OPTIONAL: training metadata not found -> {training_info}"
    )
    checks.append(
        (
            True,
            training_message,
        )
    )
    return checks


def check_rag(rag_dir: Path) -> List[Tuple[bool, str]]:
    return [
        check_file(rag_dir / "embeddings.npy", "RAG embeddings"),
        check_file(rag_dir / "metadata.jsonl", "RAG metadata"),
    ]


def check_config(config_path: Path) -> List[Tuple[bool, str]]:
    checks = [check_file(config_path, "local config")]
    if not config_path.exists():
        return checks

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config: Dict = json.load(handle)
        checks.append(("model" in config, f"{status('model' in config)}: config.model"))
        checks.append(("rag" in config, f"{status('rag' in config)}: config.rag"))
    except Exception as exc:
        checks.append((False, f"MISSING: config parse failed -> {exc}"))
    return checks


def check_optional_langgraph() -> List[Tuple[bool, str]]:
    try:
        import langgraph  # noqa: F401

        return [(True, "OK: optional langgraph import")]
    except ImportError:
        return [
            (
                False,
                "MISSING: optional langgraph import -> pip install -r requirements-langgraph.txt",
            )
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local GIS deployment readiness.")
    parser.add_argument("--model-dir", default=str(PROJECT_ROOT / "models" / "step-level-model-865"))
    parser.add_argument("--rag-dir", default=str(PROJECT_ROOT / "data" / "processed" / "rag_index"))
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "local_config.json"))
    parser.add_argument("--check-langgraph", action="store_true")
    args = parser.parse_args()

    checks: List[Tuple[bool, str]] = []
    checks.extend(check_python())
    checks.extend(check_config(Path(args.config)))
    checks.extend(check_model(Path(args.model_dir)))
    checks.extend(check_rag(Path(args.rag_dir)))
    if args.check_langgraph:
        checks.extend(check_optional_langgraph())

    print("GIS local deployment preflight")
    print("=" * 72)
    for ok, message in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {message}")

    required_failures = [
        message
        for ok, message in checks
        if not ok
        and not message.startswith("MISSING: optional langgraph")
        and not message.startswith("OPTIONAL:")
    ]
    print("=" * 72)
    if required_failures:
        print(f"Result: NOT READY ({len(required_failures)} required checks failed)")
        return 1

    print("Result: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
