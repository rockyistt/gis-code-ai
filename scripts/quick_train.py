#!/usr/bin/env python
"""
快速训练脚本 - 一键完成数据准备和模型训练

使用方式：
  python scripts/quick_train.py           # 使用默认配置
  python scripts/quick_train.py --test    # 快速测试模式
  python scripts/quick_train.py --full    # 完整训练
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class QuickTrainer:
    """快速训练工具"""
    
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.project_root = Path(__file__).parent.parent
        
    def run_command(self, cmd: list, description: str):
        """运行命令"""
        logger.info(f"🚀 {description}")
        logger.info(f"   命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, cwd=self.project_root)
        
        if result.returncode != 0:
            logger.error(f"❌ 失败: {description}")
            sys.exit(1)
        
        logger.info(f"✅ 完成: {description}")
        return result
    
    def check_dependencies(self):
        """检查依赖是否安装"""
        logger.info("🔍 检查依赖...")
        
        required_packages = ['transformers', 'peft', 'torch', 'datasets', 'accelerate']
        missing = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing.append(package)
        
        if missing:
            logger.warning(f"⚠️  缺少依赖: {', '.join(missing)}")
            logger.info("💡 安装依赖: pip install -r requirements.txt")
            
            response = input("是否现在安装？(y/n): ")
            if response.lower() == 'y':
                self.run_command(
                    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                    "安装依赖"
                )
            else:
                logger.error("❌ 请先安装依赖")
                sys.exit(1)
        else:
            logger.info("✅ 所有依赖已安装")
    
    def check_data_files(self):
        """检查数据文件是否存在"""
        logger.info("📂 检查数据文件...")
        
        instructions_file = self.project_root / "data/processed/step_level_instructions_weighted_variants_marked.jsonl"
        workflows_file = self.project_root / "data/processed/parsed_workflows.jsonl"
        
        if not instructions_file.exists():
            logger.error(f"❌ 指令文件不存在: {instructions_file}")
            logger.info("💡 请先运行: python scripts/generate_instructions_weighted.py")
            sys.exit(1)
        
        if not workflows_file.exists():
            logger.error(f"❌ 工作流文件不存在: {workflows_file}")
            logger.info("💡 请先运行工作流解析")
            sys.exit(1)
        
        logger.info("✅ 数据文件完整")
    
    def prepare_training_data(self):
        """准备训练数据"""
        cmd = [sys.executable, 'src/training/prepare_training_data.py']
        
        if self.test_mode:
            cmd.extend(['--max-samples', '1000'])
        
        self.run_command(cmd, "准备训练数据")
    
    def train_model(self):
        """训练模型"""
        cmd = [sys.executable, 'src/training/train_lora.py']
        
        if self.test_mode:
            # 测试模式：快速验证流程
            cmd.extend([
                '--num-epochs', '1',
                '--batch-size', '2',
                '--gradient-accumulation-steps', '2',
                '--save-steps', '50',
                '--logging-steps', '5',
            ])
        
        self.run_command(cmd, "LoRA微调训练")
    
    def run(self):
        """执行完整训练流程"""
        logger.info("="*70)
        logger.info("🎯 GIS代码生成模型 - 快速训练")
        logger.info("="*70)
        logger.info(f"模式: {'测试模式 (快速验证)' if self.test_mode else '完整训练'}")
        logger.info("="*70)
        
        # 1. 检查依赖
        self.check_dependencies()
        
        # 2. 检查数据
        self.check_data_files()
        
        # 3. 准备训练数据
        logger.info("\n" + "="*70)
        logger.info("步骤 1/2: 准备训练数据")
        logger.info("="*70)
        self.prepare_training_data()
        
        # 4. 训练模型
        logger.info("\n" + "="*70)
        logger.info("步骤 2/2: 训练模型")
        logger.info("="*70)
        self.train_model()
        
        # 完成
        logger.info("\n" + "="*70)
        logger.info("🎉 训练完成！")
        logger.info("="*70)
        logger.info("📦 模型位置: models/qwen-gis-lora/")
        logger.info("📊 训练数据: data/training/")
        logger.info("")
        logger.info("下一步:")
        logger.info("  1. 评估模型: python examples/evaluate_model.py")
        logger.info("  2. 测试推理: python examples/demo_inference.py")
        logger.info("="*70)


def main():
    parser = argparse.ArgumentParser(description="快速训练GIS代码生成模型")
    parser.add_argument('--test', action='store_true',
                       help='测试模式（小数据集，快速验证）')
    parser.add_argument('--full', action='store_true',
                       help='完整训练模式')
    
    args = parser.parse_args()
    
    # 默认使用测试模式
    test_mode = not args.full
    
    trainer = QuickTrainer(test_mode=test_mode)
    trainer.run()


if __name__ == "__main__":
    main()
