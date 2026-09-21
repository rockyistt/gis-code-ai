#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_inference.py - 本地推理脚本

在本地机器上运行 GIS 模型推理，无需 Colab。

使用方法：
    # 单条推理
    python local_inference.py --instruction "Open the editor"
    
    # 使用自定义参数
    python local_inference.py \\
        --instruction "Your instruction" \\
        --model-path "./models/step-level-model-865" \\
        --threshold 0.8 \\
        --output-json
    
    # 批量推理
    python local_inference.py --batch-file instructions.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


def load_config():
    """加载本地配置文件"""
    config_path = PROJECT_ROOT / "configs" / "local_config.json"
    
    if not config_path.exists():
        print("⚠️  配置文件不存在，使用默认配置")
        return {
            "model": {
                "local_path": "./models/step-level-model-865",
                "device": "auto",
            },
            "rag": {
                "index_path": "./data/processed/rag_index",
                "threshold": 0.8,
            },
            "inference": {
                "max_tokens": 1024,
            }
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def initialize_inferencer(config: Dict, model_path: str = None, rag_path: str = None):
    """初始化推理引擎"""
    try:
        from src.inference import HybridInferencer
        
        # 使用命令行参数覆盖配置文件
        model_path = model_path or config["model"]["local_path"]
        rag_path = rag_path or config["rag"]["index_path"]
        
        print(f"  🚀 加载推理引擎...")
        print(f"    • 模型: {model_path}")
        print(f"    • RAG: {rag_path}")
        
        inferencer = HybridInferencer(
            model_path=model_path,
            rag_index_path=rag_path,
            use_rag=config["rag"].get("enabled", True),
            device=config["model"].get("device", "auto"),
        )
        
        print(f"  ✅ 推理引擎已就绪")
        return inferencer
    
    except ImportError as e:
        print(f"  ❌ 导入失败: {e}")
        print(f"     请确保已安装 src.inference 模块")
        sys.exit(1)
    
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        print(f"\n  💡 故障排查:")
        print(f"     • 检查模型路径: {model_path}")
        print(f"     • 检查 RAG 索引: {rag_path}")
        print(f"     • 运行 setup_local_environment.py 初始化")
        sys.exit(1)


def infer_single(
    inferencer,
    instruction: str,
    config: Dict,
    output_json: bool = False,
    threshold: float = None,
):
    """单条推理"""
    threshold = threshold or config["rag"].get("threshold", 0.8)
    
    print(f"\n  📝 输入指令:")
    print(f"     {instruction}")
    print(f"\n  ⏳ 推理中...\n")
    
    try:
        result = inferencer.infer(
            instruction,
            rag_threshold=threshold,
            max_tokens=config["inference"].get("max_tokens", 1024),
            return_details=True
        )
        
        if output_json:
            # JSON 格式输出
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        else:
            # 友好格式输出
            print("  " + "="*66)
            print("  🎯 推理结果")
            print("  " + "="*66)
            
            print(f"\n  📊 数据源: {result['source'].upper()}")
            print(f"  📈 置信度: {result['confidence']:.4f}")
            
            if result.get('rag_score') is not None:
                print(f"  🔍 RAG 相似度: {result['rag_score']:.4f}")
            
            print(f"  📝 说明: {result['explanation']}")
            
            # 显示结果
            if isinstance(result['result'], dict):
                print(f"\n  📤 结构化结果:")
                for key, value in result['result'].items():
                    if value:
                        print(f"     • {key}: {value}")
            else:
                print(f"\n  📤 结果:")
                print(f"     {result['result']}")
            
            print(f"\n  {'='*66}\n")
        
        return result
    
    except Exception as e:
        print(f"  ❌ 推理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def infer_batch(
    inferencer,
    instructions: List[str],
    config: Dict,
    output_json: bool = False,
    threshold: float = None,
):
    """批量推理"""
    threshold = threshold or config["rag"].get("threshold", 0.8)
    
    print(f"\n  📋 批量推理 ({len(instructions)} 条指令)")
    print(f"  ⏳ 处理中...\n")
    
    results = []
    rag_count = 0
    model_count = 0
    
    try:
        for idx, instruction in enumerate(instructions, 1):
            print(f"  [{idx}/{len(instructions)}] {instruction[:50]}...")
            
            result = inferencer.infer(
                instruction,
                rag_threshold=threshold,
                return_details=False
            )
            
            results.append(result)
            
            if result['source'] == 'rag':
                rag_count += 1
                print(f"           ✅ RAG (相似度: {result['confidence']:.4f})")
            else:
                model_count += 1
                print(f"           🤖 模型")
        
        # 输出结果
        if output_json:
            output = {
                "total": len(instructions),
                "rag_count": rag_count,
                "model_count": model_count,
                "results": results
            }
            print(f"\n{json.dumps(output, indent=2, ensure_ascii=False, default=str)}")
        else:
            print(f"\n  {'='*66}")
            print(f"  📊 批量推理统计")
            print(f"  {'='*66}")
            print(f"    • 总数: {len(instructions)}")
            print(f"    • RAG 命中: {rag_count} ({rag_count/len(instructions)*100:.1f}%)")
            print(f"    • 模型推理: {model_count} ({model_count/len(instructions)*100:.1f}%)")
            print(f"  {'='*66}\n")
        
        return results
    
    except Exception as e:
        print(f"  ❌ 批量推理失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="GIS 本地模型推理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单条推理
  python local_inference.py --instruction "Open the editor"
  
  # 使用自定义参数
  python local_inference.py --instruction "Create cable" --threshold 0.7
  
  # 输出 JSON 格式
  python local_inference.py --instruction "Open editor" --output-json
  
  # 批量推理
  python local_inference.py --batch-file instructions.json
        """
    )
    
    parser.add_argument(
        "--instruction",
        type=str,
        help="单条指令"
    )
    
    parser.add_argument(
        "--batch-file",
        type=str,
        help="批量指令文件 (JSON 或 TXT)"
    )
    
    parser.add_argument(
        "--model-path",
        type=str,
        help="模型路径 (默认: ./models/step-level-model-865)"
    )
    
    parser.add_argument(
        "--rag-path",
        type=str,
        help="RAG 索引路径 (默认: ./data/processed/rag_index)"
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="RAG 相似度阈值 (默认: 0.8)"
    )
    
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="输出 JSON 格式"
    )
    
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="禁用 RAG，仅使用模型"
    )
    
    args = parser.parse_args()
    
    # 打印欢迎信息
    print("\n" + "="*70)
    print("  🚀 GIS 本地推理系统")
    print("="*70)
    
    # 加载配置
    print("\n  📂 加载配置...")
    config = load_config()
    
    if args.no_rag:
        config["rag"]["enabled"] = False
        print("  ℹ️  RAG 已禁用")
    
    # 初始化推理引擎
    print("\n  🔧 初始化推理引擎...")
    inferencer = initialize_inferencer(config, args.model_path, args.rag_path)
    
    # 执行推理
    if args.instruction:
        # 单条推理
        infer_single(
            inferencer,
            args.instruction,
            config,
            args.output_json,
            args.threshold
        )
    
    elif args.batch_file:
        # 批量推理
        batch_path = Path(args.batch_file)
        
        if not batch_path.exists():
            print(f"\n  ❌ 文件不存在: {batch_path}")
            sys.exit(1)
        
        # 加载指令
        if batch_path.suffix == '.json':
            with open(batch_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                instructions = data if isinstance(data, list) else [data]
        else:  # .txt 或其他
            with open(batch_path, 'r', encoding='utf-8') as f:
                instructions = [line.strip() for line in f if line.strip()]
        
        infer_batch(
            inferencer,
            instructions,
            config,
            args.output_json,
            args.threshold
        )
    
    else:
        # 交互模式
        print("\n  💬 交互模式 (输入 'quit' 退出)")
        print("="*70 + "\n")
        
        while True:
            try:
                instruction = input("📝 请输入指令: ").strip()
                
                if instruction.lower() in ['quit', 'exit', 'q']:
                    print("\n  👋 再见!")
                    break
                
                if not instruction:
                    continue
                
                infer_single(
                    inferencer,
                    instruction,
                    config,
                    args.output_json,
                    args.threshold
                )
            
            except KeyboardInterrupt:
                print("\n\n  👋 中断!")
                break
            except Exception as e:
                print(f"  ❌ 错误: {e}")


if __name__ == "__main__":
    main()
