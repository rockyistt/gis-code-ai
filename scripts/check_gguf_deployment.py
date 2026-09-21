#!/usr/bin/env python3
"""Check readiness for GGUF + llama.cpp local deployment."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def ok(value: bool) -> str:
    return "PASS" if value else "FAIL"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def find_llama_tool(name: str) -> str | None:
    from_path = shutil.which(name) or shutil.which(f"{name}.exe")
    if from_path:
        return from_path

    candidates = [
        PROJECT_ROOT / "external" / "llama.cpp" / "build" / "bin" / f"{name}.exe",
        PROJECT_ROOT / "external" / "llama.cpp" / "build" / "bin" / "Release" / f"{name}.exe",
        PROJECT_ROOT / "external" / "llama.cpp" / f"{name}.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check GGUF + llama.cpp deployment readiness.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "local_config.json"))
    parser.add_argument("--gguf", default=None, help="Path to quantized GGUF model.")
    parser.add_argument("--lora", default=None, help="Path to GGUF LoRA adapter.")
    parser.add_argument("--server-url", default=None, help="llama.cpp server URL.")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    llama_cfg = config.get("llama_cpp", {})
    gguf_path = Path(args.gguf or llama_cfg.get("model_path", "models/gguf/gis-step-model-Q4_K_M.gguf"))
    if not gguf_path.is_absolute():
        gguf_path = PROJECT_ROOT / gguf_path
    lora_path = Path(args.lora or llama_cfg.get("lora_path", "models/gguf/gis-step-model-lora.gguf"))
    if not lora_path.is_absolute():
        lora_path = PROJECT_ROOT / lora_path
    server_url = args.server_url or llama_cfg.get("server_url", "http://127.0.0.1:8080")

    llama_server = find_llama_tool("llama-server")
    llama_cli = find_llama_tool("llama-cli")
    llama_quantize = find_llama_tool("llama-quantize")

    checks = [
        (gguf_path.exists(), f"GGUF model -> {gguf_path}"),
        (lora_path.exists(), f"GGUF LoRA adapter -> {lora_path}"),
        (llama_server is not None, f"llama-server -> {llama_server}"),
        (llama_cli is not None, f"llama-cli -> {llama_cli}"),
        (llama_quantize is not None, f"llama-quantize -> {llama_quantize}"),
    ]

    print("GGUF + llama.cpp deployment check")
    print("=" * 72)
    for passed, message in checks:
        print(f"[{ok(passed)}] {message}")

    print("=" * 72)
    print(f"Configured server URL: {server_url}")

    if llama_server and gguf_path.exists():
        print("\nSuggested server command:")
        print(
            f'"{llama_server}" -m "{gguf_path}" --host 127.0.0.1 --port 8080 '
            f'--ctx-size 2048 --threads 8 --lora "{lora_path}"'
        )

    missing_required = [message for passed, message in checks[:3] if not passed]
    if missing_required:
        print("\nResult: NOT READY")
        return 1
    print("\nResult: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
