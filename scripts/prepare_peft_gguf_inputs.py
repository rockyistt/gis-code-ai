#!/usr/bin/env python3
"""Prepare mixed PEFT checkpoints for llama.cpp GGUF conversion.

The Colab export used for this project stores base weights and LoRA adapter
weights in one `model.safetensors` file with PEFT-style names. llama.cpp needs
either a plain Hugging Face model or a separate LoRA adapter, so this script
splits the checkpoint without loading the full 7B model into RAM.
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path

from safetensors.torch import safe_open, save_file


NON_WEIGHT_FILES = [
    "added_tokens.json",
    "config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
]


def load_safetensors_header(path: Path) -> tuple[int, dict]:
    with path.open("rb") as handle:
        header_len = struct.unpack("<Q", handle.read(8))[0]
        header = json.loads(handle.read(header_len))
    return header_len, header


def base_key(name: str) -> str | None:
    if ".lora_A." in name or ".lora_B." in name:
        return None
    if not name.startswith("base_model.model."):
        return name
    stripped = name.removeprefix("base_model.model.")
    return stripped.replace(".base_layer.weight", ".weight")


def lora_key(name: str) -> str | None:
    if ".lora_A.default.weight" not in name and ".lora_B.default.weight" not in name:
        return None
    return name.replace(".default.weight", ".weight")


def copy_file(src: Path, dst: Path, chunk_size: int = 1024 * 1024 * 32) -> None:
    with src.open("rb") as input_handle, dst.open("wb") as output_handle:
        while True:
            chunk = input_handle.read(chunk_size)
            if not chunk:
                break
            output_handle.write(chunk)


def write_streamed_base_safetensors(src: Path, dst: Path) -> int:
    original_header_len, header = load_safetensors_header(src)
    data_start = 8 + original_header_len

    selected: list[tuple[str, str, dict]] = []
    for original_name, metadata in header.items():
        if original_name == "__metadata__":
            continue
        new_name = base_key(original_name)
        if new_name is None:
            continue
        selected.append((original_name, new_name, metadata))

    new_header: dict[str, dict] = {}
    offset = 0
    for _original_name, new_name, metadata in selected:
        start, end = metadata["data_offsets"]
        size = end - start
        new_header[new_name] = {
            "dtype": metadata["dtype"],
            "shape": metadata["shape"],
            "data_offsets": [offset, offset + size],
        }
        offset += size

    header_bytes = json.dumps(new_header, separators=(",", ":")).encode("utf-8")
    dst.parent.mkdir(parents=True, exist_ok=True)

    with src.open("rb") as input_handle, dst.open("wb") as output_handle:
        output_handle.write(struct.pack("<Q", len(header_bytes)))
        output_handle.write(header_bytes)

        for original_name, _new_name, metadata in selected:
            start, end = metadata["data_offsets"]
            input_handle.seek(data_start + start)
            remaining = end - start
            while remaining:
                chunk = input_handle.read(min(remaining, 1024 * 1024 * 32))
                if not chunk:
                    raise EOFError(f"Unexpected EOF while copying {original_name}")
                output_handle.write(chunk)
                remaining -= len(chunk)

    return len(selected)


def sync_config_from_tensor_shapes(source_weights: Path, base_dir: Path) -> None:
    _header_len, header = load_safetensors_header(source_weights)
    config_path = base_dir / "config.json"
    if not config_path.exists():
        return

    config = json.loads(config_path.read_text(encoding="utf-8"))
    changed = False

    embed = header.get("base_model.model.model.embed_tokens.weight") or header.get("model.embed_tokens.weight")
    if embed:
        vocab_size = embed["shape"][0]
        if config.get("vocab_size") != vocab_size:
            config["vocab_size"] = vocab_size
            changed = True
            print(f"Updated prepared config vocab_size to {vocab_size}")

    k_proj = header.get("base_model.model.model.layers.0.self_attn.k_proj.weight")
    hidden_size = config.get("hidden_size")
    num_attention_heads = config.get("num_attention_heads")
    if k_proj and hidden_size and num_attention_heads:
        head_dim = hidden_size // num_attention_heads
        inferred_kv_heads = k_proj["shape"][0] // head_dim
        if config.get("num_key_value_heads") != inferred_kv_heads:
            config["num_key_value_heads"] = inferred_kv_heads
            changed = True
            print(f"Updated prepared config num_key_value_heads to {inferred_kv_heads}")

    if changed:
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def write_lora_adapter(src: Path, adapter_dir: Path) -> int:
    tensors = {}
    with safe_open(src, framework="pt", device="cpu") as handle:
        for key in handle.keys():
            new_key = lora_key(key)
            if new_key is not None:
                tensors[new_key] = handle.get_tensor(key)

    if not tensors:
        return 0

    adapter_dir.mkdir(parents=True, exist_ok=True)
    save_file(tensors, adapter_dir / "adapter_model.safetensors")
    return len(tensors)


def copy_metadata_files(model_dir: Path, base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for name in NON_WEIGHT_FILES:
        source = model_dir / name
        if source.exists():
            shutil.copy2(source, base_dir / name)

    tokenizer_dir = model_dir / "tokenizer"
    if tokenizer_dir.exists():
        destination = base_dir / "tokenizer"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(tokenizer_dir, destination)


def write_adapter_config(model_dir: Path, adapter_dir: Path) -> None:
    training_info_path = model_dir / "training_info.json"
    training_info = {}
    if training_info_path.exists():
        training_info = json.loads(training_info_path.read_text(encoding="utf-8"))

    config = {
        "base_model_name_or_path": training_info.get("model_name", "codellama/CodeLlama-7b-Instruct-hf"),
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "lora_alpha": training_info.get("lora_alpha", 32),
        "lora_dropout": training_info.get("lora_dropout", 0.0),
        "peft_type": "LORA",
        "r": training_info.get("lora_r", 64),
        "target_modules": ["q_proj", "v_proj"],
        "task_type": "CAUSAL_LM",
    }
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Split mixed PEFT checkpoint for GGUF conversion.")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    out_dir = args.out_dir.resolve()
    source_weights = model_dir / "model.safetensors"
    if not source_weights.exists():
        raise FileNotFoundError(source_weights)

    base_dir = out_dir / "hf-base"
    adapter_dir = out_dir / "lora-adapter"
    base_weights = base_dir / "model.safetensors"

    copy_metadata_files(model_dir, base_dir)
    sync_config_from_tensor_shapes(source_weights, base_dir)
    base_count = write_streamed_base_safetensors(source_weights, base_weights)
    lora_count = write_lora_adapter(source_weights, adapter_dir)
    if lora_count:
        write_adapter_config(model_dir, adapter_dir)

    print(f"Prepared base model: {base_dir} ({base_count} tensors)")
    if lora_count:
        print(f"Prepared LoRA adapter: {adapter_dir} ({lora_count} tensors)")
    else:
        print("No LoRA adapter tensors found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
