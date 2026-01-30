"""
文件级训练数据准备脚本

将file_level_instructions转换为训练格式
每个样本对应一个完整的工作流（包含所有steps的JSON）

优势：
- 模型学习完整工作流的结构
- 输出是实际可用的测试脚本
- 符合GIS平台使用场景（一次性生成完整工作流）
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FileeLevelTrainingDataPreparer:
    """文件级训练数据准备器"""
    
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
    
    def convert_file_to_training_sample(self, file_instr: Dict, workflow: Dict) -> Dict:
        """
        将文件级指令转换为训练样本
        
        Args:
            file_instr: 文件级指令（包含instruction）
            workflow: 原始工作流数据（包含所有steps）
        
        Returns:
            训练样本 {instruction, input, output}
        """
        # 获取指令
        instruction = self.clean_instruction(file_instr.get('instruction', ''))
        
        # 构建输入上下文
        input_context = self._build_context(file_instr, workflow)
        
        # 获取输出：完整的工作流JSON（包含所有steps）
        output_code = self._extract_workflow_json(workflow)
        
        return {
            "instruction": instruction,
            "input": input_context,
            "output": output_code
        }
    
    def _build_context(self, file_instr: Dict, workflow: Dict) -> str:
        """
        构建输入上下文
        
        包含：
        - 应用类型（test_app）
        - 数据库类型
        - 工作流统计
        """
        context_parts = []
        
        # 应用类型
        test_app = workflow.get('test_app', '')
        if test_app:
            context_parts.append(f"Application: {test_app}")
        
        # 数据库
        database = workflow.get('database', '')
        if database:
            context_parts.append(f"Database: {database}")
        
        # 步骤数量
        total_steps = workflow.get('total_steps', 0)
        if total_steps > 0:
            context_parts.append(f"Steps: {total_steps}")
        
        # 对象类型
        objects = workflow.get('objects', [])
        if objects:
            obj_str = ', '.join(objects[:3])  # 最多显示3个对象
            context_parts.append(f"Objects: {obj_str}")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def _extract_workflow_json(self, workflow: Dict) -> str:
        """
        提取完整的工作流JSON
        
        包含所有steps，这是模型需要学习生成的完整结构
        """
        steps = workflow.get('steps', [])
        
        if not steps:
            return "{}"
        
        # 创建工作流结构
        workflow_output = {
            "workflow": {
                "metadata": {
                    "test_app": workflow.get('test_app', ''),
                    "database": workflow.get('database', ''),
                    "total_steps": len(steps)
                },
                "steps": steps
            }
        }
        
        return json.dumps(workflow_output, indent=2, ensure_ascii=False)
    
    def prepare_dataset(self, instructions_file: str, workflows_file: str,
                       output_file: str, max_samples: int = None,
                       split_ratio: float = 0.9):
        """
        准备完整的文件级训练数据集
        
        Args:
            instructions_file: 文件级指令文件路径
            workflows_file: 原始工作流文件路径
            output_file: 输出文件路径
            max_samples: 最大样本数（用于测试）
            split_ratio: 训练集比例（0.9 = 90%训练，10%验证）
        """
        logger.info(f"📖 Loading file-level instructions...")
        
        # 加载指令数据
        instructions = {}
        with open(instructions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    file_id = item.get('file_id', '')
                    instructions[file_id] = item
        
        logger.info(f"✅ Loaded {len(instructions)} file-level instructions")
        
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
        
        logger.info("🔄 Converting to training format (file-level)...")
        
        processed_count = 0
        for file_id, instr in tqdm(instructions.items(), desc="Processing"):
            workflow = workflows.get(file_id, {})
            
            if not workflow:
                continue
            
            # 转换
            sample = self.convert_file_to_training_sample(instr, workflow)
            
            # 质量过滤
            if self._is_valid_sample(sample):
                training_samples.append(sample)
            
            processed_count += 1
            
            # 限制数量
            if max_samples and processed_count >= max_samples:
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
            "data_level": "file-level",
            "avg_instruction_length": sum(len(s['instruction'].split()) for s in training_samples) / len(training_samples) if training_samples else 0,
            "avg_output_length": sum(len(s['output']) for s in training_samples) / len(training_samples) if training_samples else 0,
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
        
        # 检查指令长度（5-300词）
        instruction_length = len(sample['instruction'].split())
        if instruction_length < 5 or instruction_length > 300:
            return False
        
        # 检查输出不为空JSON
        if sample['output'] == '{}':
            return False
        
        # 检查输出包含"workflow"关键词
        if '"workflow"' not in sample['output']:
            return False
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="准备文件级模型训练数据")
    parser.add_argument('--instructions', type=str,
                       default='data/processed/file_level_instructions_weighted_variants_marked.jsonl',
                       help='文件级指令文件路径')
    parser.add_argument('--workflows', type=str,
                       default='data/processed/parsed_workflows.jsonl',
                       help='原始工作流文件路径')
    parser.add_argument('--output', type=str,
                       default='data/training/file_level_training_data.json',
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
    preparer = FileeLevelTrainingDataPreparer(remove_weight_markers=not args.keep_markers)
    
    train_data, val_data, stats = preparer.prepare_dataset(
        instructions_file=args.instructions,
        workflows_file=args.workflows,
        output_file=args.output,
        max_samples=args.max_samples,
        split_ratio=args.split_ratio
    )
    
    # 输出摘要
    logger.info("\n" + "="*70)
    logger.info("🎉 文件级数据准备完成！")
    logger.info("="*70)
    logger.info(f"📊 统计:")
    logger.info(f"  - 数据粒度: 文件级（完整工作流）")
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
        logger.info(f"  Output: {sample['output'][:200]}...")


if __name__ == "__main__":
    main()
