#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断脚本：检查 Google Drive 中模型文件的实际结构
（用于对比 download_model_from_gdrive.py 中的验证逻辑）
"""

import os
from pathlib import Path

print("="*70)
print("🔍 诊断 Google Drive 模型文件结构")
print("="*70)

# 检查本地已下载的模型
model_dir = Path(__file__).parent.parent / "models" / "step-level-model-865"

if not model_dir.exists():
    print(f"\n❌ 模型目录不存在：{model_dir}")
    print("   请先运行 download_model_from_gdrive.py")
    exit(1)

print(f"\n📁 检查目录：{model_dir}\n")

# 列出所有文件
all_files = []
for root, dirs, files in os.walk(model_dir):
    for file in files:
        fpath = Path(root) / file
        rel_path = fpath.relative_to(model_dir)
        size_mb = fpath.stat().st_size / (1024**2)
        all_files.append((str(rel_path), size_mb))

if not all_files:
    print("❌ 模型目录为空！")
    exit(1)

# 分类显示
print("📋 模型文件清单：\n")

# 配置文件
config_files = [f for f in all_files if f[0].endswith('.json')]
print("📄 配置文件 (JSON):")
for fname, size in config_files:
    print(f"   • {fname} ({size:.2f} MB)")

# 权重文件
weight_files = [f for f in all_files if f[0].endswith(('.bin', '.safetensors'))]
print("\n⚖️  权重文件 (bin/safetensors):")
for fname, size in weight_files:
    print(f"   • {fname} ({size:.2f} MB)")

# Tokenizer 文件
tokenizer_files = [f for f in all_files if 'token' in f[0].lower()]
print("\n🔤 Tokenizer 文件:")
for fname, size in tokenizer_files:
    print(f"   • {fname} ({size:.2f} MB)")

# 其他文件
other_files = [f for f in all_files if f not in config_files + weight_files + tokenizer_files]
if other_files:
    print("\n📦 其他文件:")
    for fname, size in other_files:
        print(f"   • {fname} ({size:.2f} MB)")

print("\n" + "="*70)
print("✅ 关键文件检查\n")

# 检查关键文件
key_checks = {
    "adapter_config.json": "LoRA 配置（必需）",
    "adapter_model.bin": "LoRA 权重（方案2需要）",
    "model.safetensors": "完整模型权重（方案1需要）",
    "pytorch_model.bin": "完整模型权重（备选）",
    "tokenizer.model": "Tokenizer 模型文件",
    "tokenizer.json": "Tokenizer JSON 文件（备选）",
    "tokenizer_config.json": "Tokenizer 配置（必需）",
}

print("文件检查状态：\n")
for fname, description in key_checks.items():
    fpath = model_dir / fname
    if fpath.exists():
        size_mb = fpath.stat().st_size / (1024**2)
        print(f"   ✅ {fname:<25} ({size_mb:>8.2f} MB)  — {description}")
    else:
        print(f"   ❌ {fname:<25} (缺失)        — {description}")

print("\n" + "="*70)
print("🔧 推荐加载方案\n")

# 判断应该用哪个方案
has_adapter_config = (model_dir / "adapter_config.json").exists()
has_model_safetensors = (model_dir / "model.safetensors").exists()
has_pytorch_bin = (model_dir / "pytorch_model.bin").exists()
has_adapter_bin = (model_dir / "adapter_model.bin").exists()

if has_adapter_config and has_adapter_bin:
    print("✅ 方案2：LoRA 加载")
    print("   • 需要下载基础模型：codellama/CodeLlama-7b-Instruct-hf")
    print("   • 使用 PEFT 加载 LoRA adapter")
    print("   • 内存占用：~15-20 GB（GPU）/ ~8 GB（CPU int8）")
elif has_model_safetensors:
    print("✅ 方案1：完整合并模型")
    print("   • 直接加载 model.safetensors")
    print("   • 内存占用：~15 GB")
elif has_pytorch_bin:
    print("✅ 方案1-备选：PyTorch 格式")
    print("   • 直接加载 pytorch_model.bin")
    print("   • 内存占用：~15 GB")
else:
    print("❌ 无法判断加载方案！缺少关键权重文件。")
    print("   请检查 Google Drive 文件夹是否完整。")

print("\n" + "="*70)
print("📊 总统计\n")
print(f"   总文件数：{len(all_files)}")
print(f"   总大小：{sum(f[1] for f in all_files):.2f} MB")
print("\n" + "="*70)
