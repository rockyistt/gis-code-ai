"""
将生成的指令数据转换为训练格式

输入：step_level_instructions_weighted_variants_marked.jsonl
输出：training_data.json (Alpaca格式)

格式：
{
    "instruction": "用户指令",
    "input": "上下文信息（可选）",
    "output": "目标JSON代码"
}
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TrainingDataPreparer:
    """训练数据准备器"""
    
    def __init__(self, remove_weight_markers: bool = True):
        """
        Args:
            remove_weight_markers: 是否移除权重标记（**关键** -> 关键）
        """
        self.remove_weight_markers = remove_weight_markers
    
    def clean_instruction(self, instruction: str) -> str:
        """清理指令文本"""
        if self.remove_weight_markers:
            # 移除权重标记
            instruction = instruction.replace('**', '').replace('*', '')
        
        # 去除多余空格
        instruction = ' '.join(instruction.split())
        
        return instruction.strip()
    
    def convert_step_to_training_sample(self, step: Dict, workflow: Dict) -> Dict:
        """
        将步骤转换为训练样本
        
        Args:
            step: 步骤数据（包含instruction）
            workflow: 原始工作流数据（包含JSON代码）
        
        Returns:
            训练样本 {instruction, input, output}
        """
        # 获取指令
        instruction = self.clean_instruction(step.get('instruction', ''))
        
        # 构建输入上下文（可选）
        input_context = self._build_context(step, workflow)
        
        # 获取输出JSON代码
        output_code = self._extract_step_code(step, workflow)
        
        return {
            "instruction": instruction,
            "input": input_context,
            "output": output_code
        }
    
    def _build_context(self, step: Dict, workflow: Dict) -> str:
        """
        构建输入上下文
        
        包含：
        - 工作流类型（test_app）
        - 当前步骤在工作流中的位置
        - 前序步骤的摘要（可选）
        """
        context_parts = []
        
        # 应用类型
        test_app = workflow.get('test_app', '')
        if test_app:
            context_parts.append(f"Application: {test_app}")
        
        # 步骤位置
        step_index = step.get('step_index', 0)
        total_steps = workflow.get('total_steps', 0)
        if total_steps > 0:
            context_parts.append(f"Step {step_index + 1} of {total_steps}")
        
        # 数据库上下文
        database = workflow.get('database', '')
        if database:
            context_parts.append(f"Database: {database}")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def _extract_step_code(self, step: Dict, workflow: Dict) -> str:
        """
        提取步骤对应的JSON代码
        
        从原始工作流的steps数组中提取对应步骤的JSON
        """
        step_index = step.get('step_index', 0)
        steps = workflow.get('steps', [])
        
        if 0 <= step_index < len(steps):
            step_data = steps[step_index]
            # 格式化JSON输出
            return json.dumps(step_data, indent=2, ensure_ascii=False)
        
        return "{}"
    
    def prepare_dataset(self, instructions_file: str, workflows_file: str,
                       output_file: str, max_samples: int = None,
                       split_ratio: float = 0.9):
        """
        准备完整的训练数据集
        
        Args:
            instructions_file: 指令文件路径
            workflows_file: 原始工作流文件路径
            output_file: 输出文件路径
            max_samples: 最大样本数（用于测试）
            split_ratio: 训练集比例（0.9 = 90%训练，10%验证）
        """
        logger.info(f"📖 Loading data...")
        
        # 加载指令数据
        instructions = []
        with open(instructions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    instructions.append(json.loads(line))
        
        logger.info(f"✅ Loaded {len(instructions)} instructions")
        
        # 加载原始工作流
        workflows = {}
        with open(workflows_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    wf = json.loads(line)
                    workflows[wf.get('file_id', '')] = wf
        
        logger.info(f"✅ Loaded {len(workflows)} workflows")
        
        # 转换为训练样本
        training_samples = []
        
        logger.info("🔄 Converting to training format...")
        for instr in tqdm(instructions, desc="Processing"):
            file_id = instr.get('file_id', '')
            workflow = workflows.get(file_id, {})
            
            if not workflow:
                continue
            
            # 转换
            sample = self.convert_step_to_training_sample(instr, workflow)
            
            # 质量过滤
            if self._is_valid_sample(sample):
                training_samples.append(sample)
            
            # 限制数量
            if max_samples and len(training_samples) >= max_samples:
                break
        
        logger.info(f"✅ Created {len(training_samples)} training samples")
        
        # 划分训练集和验证集
        split_idx = int(len(training_samples) * split_ratio)
        train_data = training_samples[:split_idx]
        val_data = training_samples[split_idx:]
        
        logger.info(f"📊 Split: {len(train_data)} train, {len(val_data)} validation")
        
        # 保存数据
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 训练集
        train_file = output_path.parent / f"{output_path.stem}_train.json"
        with open(train_file, 'w', encoding='utf-8') as f:
            json.dump(train_data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Train data saved: {train_file}")
        
        # 验证集
        val_file = output_path.parent / f"{output_path.stem}_val.json"
        with open(val_file, 'w', encoding='utf-8') as f:
            json.dump(val_data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Validation data saved: {val_file}")
        
        # 保存统计信息
        stats = {
            "total_samples": len(training_samples),
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "split_ratio": split_ratio,
            "source_instructions": instructions_file,
            "source_workflows": workflows_file,
            "avg_instruction_length": sum(len(s['instruction'].split()) for s in training_samples) / len(training_samples),
            "avg_output_length": sum(len(s['output']) for s in training_samples) / len(training_samples),
        }
        
        stats_file = output_path.parent / f"{output_path.stem}_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        logger.info(f"📈 Statistics saved: {stats_file}")
        
        return train_data, val_data, stats
    
    def _is_valid_sample(self, sample: Dict) -> bool:
        """验证样本质量"""
        # 检查必要字段
        if not sample.get('instruction') or not sample.get('output'):
            return False
        
        # 检查指令长度（5-200词）
        instruction_length = len(sample['instruction'].split())
        if instruction_length < 5 or instruction_length > 200:
            return False
        
        # 检查输出不为空
        if sample['output'] == '{}':
            return False
        
        return True


def main():
    parser = argparse.ArgumentParser(description="准备模型训练数据")
    parser.add_argument('--instructions', type=str,
                       default='data/processed/step_level_instructions_weighted_variants_marked.jsonl',
                       help='指令文件路径')
    parser.add_argument('--workflows', type=str,
                       default='data/processed/parsed_workflows.jsonl',
                       help='原始工作流文件路径')
    parser.add_argument('--output', type=str,
                       default='data/training/training_data.json',
                       help='输出文件路径（不含_train/_val后缀）')
    parser.add_argument('--max-samples', type=int,
                       help='最大样本数（用于测试）')
    parser.add_argument('--split-ratio', type=float, default=0.9,
                       help='训练集比例（默认0.9）')
    parser.add_argument('--keep-markers', action='store_true',
                       help='保留权重标记（**关键**）')
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.instructions).exists():
        logger.error(f"❌ Instructions file not found: {args.instructions}")
        return
    
    if not Path(args.workflows).exists():
        logger.error(f"❌ Workflows file not found: {args.workflows}")
        return
    
    # 准备数据
    preparer = TrainingDataPreparer(remove_weight_markers=not args.keep_markers)
    
    train_data, val_data, stats = preparer.prepare_dataset(
        instructions_file=args.instructions,
        workflows_file=args.workflows,
        output_file=args.output,
        max_samples=args.max_samples,
        split_ratio=args.split_ratio
    )
    
    # 输出摘要
    logger.info("\n" + "="*70)
    logger.info("🎉 数据准备完成！")
    logger.info("="*70)
    logger.info(f"📊 统计:")
    logger.info(f"  - 训练样本: {stats['train_samples']:,}")
    logger.info(f"  - 验证样本: {stats['val_samples']:,}")
    logger.info(f"  - 平均指令长度: {stats['avg_instruction_length']:.1f} 词")
    logger.info(f"  - 平均输出长度: {stats['avg_output_length']:.1f} 字符")
    logger.info("="*70)
    
    # 显示示例
    if train_data:
        logger.info("\n📝 训练样本示例:")
        sample = train_data[0]
        logger.info(f"  Instruction: {sample['instruction'][:100]}...")
        logger.info(f"  Input: {sample['input']}")
        logger.info(f"  Output: {sample['output'][:150]}...")


if __name__ == "__main__":
    main()
