#!/usr/bin/env python3
"""Smoke test the local fine-tuned GIS step model.

By default this script only checks files, imports, tokenizer loading, and GPU
visibility. Use --load-model when you are ready to load the 7B weights locally.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
    sys.stdout.flush()


def check_model_files(model_dir: Path) -> None:
    print_section("1. Model Files")
    required_any_weight = ["model.safetensors", "pytorch_model.bin", "adapter_model.bin", "adapter_model.safetensors"]
    tokenizer_files = ["tokenizer.json", "tokenizer.model", "tokenizer_config.json"]

    print(f"model_dir: {model_dir}")
    print(f"exists: {model_dir.exists()}")

    for name in [
        "config.json",
        "model.safetensors",
        "pytorch_model.bin",
        "adapter_config.json",
        "adapter_model.bin",
        "adapter_model.safetensors",
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
        "training_info.json",
    ]:
        path = model_dir / name
        if path.exists():
            size = path.stat().st_size / (1024 ** 2)
            print(f"[OK]   {name:<28} {size:>10.2f} MB")
        else:
            print(f"[MISS] {name}")
    sys.stdout.flush()

    has_weight = any((model_dir / name).exists() for name in required_any_weight)
    has_tokenizer = any((model_dir / name).exists() for name in tokenizer_files)
    if not has_weight:
        raise FileNotFoundError("No model or adapter weights found.")
    if not has_tokenizer:
        raise FileNotFoundError("No tokenizer artifacts found.")


def check_imports() -> None:
    print_section("2. Python Imports")
    import torch
    import transformers
    import peft
    import safetensors

    print(f"torch:        {torch.__version__}")
    print(f"transformers: {transformers.__version__}")
    print(f"peft:         {peft.__version__}")
    print(f"safetensors:  {safetensors.__version__}")
    print(f"cuda:         {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"gpu:          {torch.cuda.get_device_name(0)}")
    sys.stdout.flush()


def check_tokenizer(model_dir: Path) -> None:
    print_section("3. Tokenizer")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    encoded = tokenizer("Create E MS Installatie FP", return_tensors="pt")
    print(f"tokenizer class: {tokenizer.__class__.__name__}")
    print(f"vocab size:      {len(tokenizer)}")
    print(f"input tokens:    {encoded['input_ids'].shape[-1]}")
    sys.stdout.flush()


def inspect_training_info(model_dir: Path) -> None:
    print_section("4. Training Info")
    info_path = model_dir / "training_info.json"
    if not info_path.exists():
        print("training_info.json not found")
        return

    with open(info_path, "r", encoding="utf-8") as handle:
        info = json.load(handle)
    for key in [
        "model_name",
        "data_level",
        "train_samples",
        "val_samples",
        "lora_r",
        "lora_alpha",
        "training_date",
    ]:
        print(f"{key}: {info.get(key)}")


def check_resources(model_dir: Path) -> None:
    print_section("5. Local Resource Estimate")
    weight_path = model_dir / "model.safetensors"
    if not weight_path.exists():
        print("No full model.safetensors found; resource estimate skipped.")
        return

    weight_gb = weight_path.stat().st_size / (1024 ** 3)
    print(f"model.safetensors size: {weight_gb:.2f} GB")

    if platform.system().lower() == "windows":
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_OperatingSystem | "
                    "Select-Object -ExpandProperty FreePhysicalMemory"
                ),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                free_kb = int(result.stdout.strip().splitlines()[-1])
                free_gb = free_kb / (1024 ** 2)
                print(f"free physical memory: {free_gb:.2f} GB")
                if free_gb < weight_gb * 1.5:
                    print(
                        "warning: free memory is likely too low for safe CPU loading. "
                        "Use GPU, more RAM, or a quantized/GGUF export."
                    )
            else:
                print("free memory check unavailable")
        except Exception as exc:
            print(f"free memory check unavailable: {exc}")
    else:
        print("memory estimate only reports exact free RAM on Windows for now.")


def load_and_predict(model_dir: Path, instruction: str, quantization: str | None, max_tokens: int) -> None:
    print_section("5. Model Load And Prediction")
    from src.inference.step_llm_predictor import StepLevelPredictor

    predictor = StepLevelPredictor(
        model_dir=str(model_dir),
        verbose=True,
        quantization=quantization,
    )
    result = predictor.predict_step(instruction, max_tokens=max_tokens)
    print("\nPrediction:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test local GIS fine-tuned model.")
    parser.add_argument("--model-dir", default=str(PROJECT_ROOT / "models" / "step-level-model-865"))
    parser.add_argument("--instruction", default="Create E MS Installatie FP")
    parser.add_argument("--load-model", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--quantization", choices=["int4", "int8"], default=None)
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    check_model_files(model_dir)
    check_imports()
    check_tokenizer(model_dir)
    inspect_training_info(model_dir)
    check_resources(model_dir)

    if args.load_model:
        load_and_predict(model_dir, args.instruction, args.quantization, args.max_tokens)
    else:
        print_section("6. Model Load Skipped")
        print("Use --load-model to load the 7B weights and run one prediction.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
