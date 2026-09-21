#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整测试脚本：验证模型下载、加载和推理
"""

import os
import sys
from pathlib import Path

def diagnose_model_files():
    """诊断模型文件"""
    print("\n" + "="*70)
    print("📁 第一步：诊断模型文件结构")
    print("="*70)
    
    model_dir = Path(__file__).parent.parent / "models" / "step-level-model-865"
    
    if not model_dir.exists():
        print(f"\n❌ 模型目录不存在：{model_dir}")
        print("   请先运行：python scripts/download_model_from_gdrive.py")
        return False
    
    print(f"\n✅ 模型目录存在：{model_dir}")
    
    # 检查关键文件
    print("\n🔍 关键文件检查：")
    
    scheme1_weights = {
        "model.safetensors": model_dir / "model.safetensors",
        "pytorch_model.bin": model_dir / "pytorch_model.bin"
    }
    
    scheme2_files = {
        "adapter_config.json": model_dir / "adapter_config.json",
        "adapter_model.bin": model_dir / "adapter_model.bin"
    }
    
    tokenizer_files = {
        "tokenizer.json": model_dir / "tokenizer.json",
        "tokenizer.model": model_dir / "tokenizer.model",
        "tokenizer_config.json": model_dir / "tokenizer_config.json"
    }
    
    # Scheme 1
    print("\n  方案1（完整模型）：")
    has_scheme1 = False
    for name, fpath in scheme1_weights.items():
        if fpath.exists():
            size = fpath.stat().st_size / (1024**3)
            print(f"    ✅ {name} ({size:.2f} GB)")
            has_scheme1 = True
        else:
            print(f"    ❌ {name}")
    
    # Scheme 2
    print("\n  方案2（LoRA 适配器）：")
    has_scheme2 = all((model_dir / name).exists() for name in scheme2_files.keys())
    for name, fpath in scheme2_files.items():
        if fpath.exists():
            size = fpath.stat().st_size / (1024**2)
            print(f"    ✅ {name} ({size:.2f} MB)")
        else:
            print(f"    ❌ {name}")
    
    # Tokenizer
    print("\n  Tokenizer 文件：")
    has_tokenizer = False
    for name, fpath in tokenizer_files.items():
        if fpath.exists():
            size = fpath.stat().st_size / (1024**2)
            print(f"    ✅ {name} ({size:.2f} MB)")
            has_tokenizer = True
        else:
            print(f"    ❌ {name}")
    
    if not (has_scheme1 or has_scheme2):
        print("\n❌ 错误：没有检测到有效的模型文件！")
        return False
    
    if not has_tokenizer:
        print("\n❌ 错误：缺少 Tokenizer 文件！")
        return False
    
    print("\n✅ 文件诊断完成")
    return has_scheme1 or has_scheme2


def test_model_loading():
    """测试模型加载"""
    print("\n" + "="*70)
    print("🚀 第二步：测试模型加载")
    print("="*70)
    
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        from src.inference.step_llm_predictor import StepLevelPredictor
        
        print("\n[INFO] 初始化 StepLevelPredictor...")
        predictor = StepLevelPredictor(
            model_dir="models/step-level-model-865",
            verbose=True
        )
        
        print("\n✅ 模型加载成功！")
        return predictor
        
    except Exception as e:
        print(f"\n❌ 模型加载失败：{e}")
        import traceback
        traceback.print_exc()
        return None


def test_inference(predictor):
    """测试推理功能"""
    print("\n" + "="*70)
    print("🧪 第三步：测试推理")
    print("="*70)
    
    test_instructions = [
        "Create E MS Installatie FP",
        "Update the object attributes",
        "Delete E MS Rail FP"
    ]
    
    for instruction in test_instructions:
        print(f"\n📝 输入：{instruction}")
        try:
            result = predictor.predict_step(instruction, max_tokens=512)
            
            if result:
                print(f"✅ 推理成功！")
                print(f"   输出长度：{len(str(result))} 字符")
                
                # 尝试显示部分结果
                import json
                try:
                    formatted = json.dumps(result, indent=2, ensure_ascii=False)
                    lines = formatted.split('\n')[:10]  # 显示前10行
                    for line in lines:
                        print(f"   {line}")
                    if len(formatted.split('\n')) > 10:
                        print("   ...")
                except:
                    print(f"   {str(result)[:200]}...")
            else:
                print(f"⚠️  推理返回 None")
                
        except Exception as e:
            print(f"❌ 推理失败：{e}")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("🔧 GIS 步骤级模型完整测试")
    print("="*70)
    
    # Step 1: 诊断文件
    if not diagnose_model_files():
        print("\n❌ 文件诊断失败，无法继续")
        sys.exit(1)
    
    # Step 2: 测试加载
    predictor = test_model_loading()
    if predictor is None:
        print("\n❌ 模型加载失败，无法继续")
        sys.exit(1)
    
    # Step 3: 测试推理
    try:
        test_inference(predictor)
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被中断")
    except Exception as e:
        print(f"\n❌ 推理测试失败：{e}")
    
    print("\n" + "="*70)
    print("✅ 所有测试完成！")
    print("="*70)
    print("\n💡 下一步：")
    print("   • 集成到 scaffolder：python examples/demo_interactive.py")
    print("   • 或者单独使用：from src.inference.step_llm_predictor import StepLevelPredictor")
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
