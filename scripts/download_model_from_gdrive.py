#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载 Google Drive 中的模型权重到本地
URL: https://drive.google.com/drive/folders/14VU2n1IdQFtFn9qkNunqN6Nhno5jsJS4
"""

import os
import sys
from pathlib import Path

# 检查是否已安装 gdown
try:
    import gdown
except ImportError:
    print("❌ gdown 未安装。正在安装...")
    os.system(f"{sys.executable} -m pip install -q gdown")
    import gdown

print("="*70)
print("📥 下载 GIS Step-Level 模型权重")
print("="*70)

# Google Drive 文件夹 ID
FOLDER_ID = "14VU2n1IdQFtFn9qkNunqN6Nhno5jsJS4"
FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"

# 本地目标路径
LOCAL_DIR = Path(__file__).parent.parent / "models" / "step-level-model-865"
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

print(f"\n📍 目标路径: {LOCAL_DIR}")
print(f"🔗 Google Drive URL: {FOLDER_URL}")

print("\n⏳ 开始下载...")
print("   首次下载需要进行 Google Drive 认证（浏览器会打开）")
print("   如需跳过认证，访问链接后右键分享链接中的 ID\n")

try:
    # 使用 gdown 下载整个文件夹
    gdown.download_folder(
        url=FOLDER_URL,
        output=str(LOCAL_DIR),
        quiet=False,
        use_cookies=False
    )
    print("\n✅ 下载完成！")
    
    # 验证重要文件（根据 052_Reload_model_and_test.ipynb 中的实际加载逻辑）
    print("\n🔍 验证文件（支持两种加载方案）...")
    
    # 方案1 的必需文件：完整模型文件 + tokenizer
    scheme1_files = {
        "model.safetensors": "完整模型权重",
        "pytorch_model.bin": "完整模型权重（备选）"
    }
    
    # 方案2 的必需文件：LoRA adapter
    scheme2_files = {
        "adapter_config.json": "LoRA 配置",
        "adapter_model.bin": "LoRA 权重"
    }
    
    # Tokenizer 文件（通用）
    tokenizer_files = {
        "tokenizer.json": "Tokenizer JSON",
        "tokenizer.model": "Tokenizer 模型文件",
        "tokenizer_config.json": "Tokenizer 配置"
    }
    
    print("\n📋 方案1 - 完整合并模型:")
    has_scheme1_weights = False
    for fname, desc in scheme1_files.items():
        fpath = LOCAL_DIR / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024**2)
            print(f"   ✅ {fname} ({size_mb:.2f} MB) — {desc}")
            has_scheme1_weights = True
        else:
            print(f"   ❌ {fname} (缺失) — {desc}")
    
    print("\n📋 方案2 - LoRA 适配器:")
    has_scheme2 = True
    for fname, desc in scheme2_files.items():
        fpath = LOCAL_DIR / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024**2)
            print(f"   ✅ {fname} ({size_mb:.2f} MB) — {desc}")
        else:
            print(f"   ❌ {fname} (缺失) — {desc}")
            has_scheme2 = False
    
    print("\n📋 Tokenizer 文件:")
    has_tokenizer = False
    for fname, desc in tokenizer_files.items():
        fpath = LOCAL_DIR / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024**2)
            print(f"   ✅ {fname} ({size_mb:.2f} MB) — {desc}")
            has_tokenizer = True
        else:
            print(f"   ❌ {fname} (缺失) — {desc}")
    
    # 总结
    print("\n" + "="*70)
    if (has_scheme1_weights or has_scheme2) and has_tokenizer:
        print("✅ 模型下载完成！")
        if has_scheme1_weights:
            print("   推荐加载方案：方案1 (完整模型，加载速度快)")
        if has_scheme2:
            print("   备选加载方案：方案2 (LoRA 适配器，内存占用更少)")
    else:
        print("⚠️  警告：部分关键文件缺失，模型可能无法正常加载")
        print("   • 请检查 Google Drive 文件夹是否完整")
        print("   • 或运行 scripts/diagnose_model_structure.py 诊断")
        
except Exception as e:
    print(f"\n❌ 下载失败: {e}")
    print("\n💡 备选方案：")
    print("   1. 手动下载 https://drive.google.com/drive/folders/14VU2n1IdQFtFn9qkNunqN6Nhno5jsJS4")
    print(f"   2. 解压到 {LOCAL_DIR}")
    print("   3. 运行 scripts/diagnose_model_structure.py 验证文件")
    sys.exit(1)

print("\n" + "="*70)
