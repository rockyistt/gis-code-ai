#!/usr/bin/env python3
"""
Step 2: 准备训练数据格式

将分离的指令和数据组合为标准的训练格式

输入: 
- data/processed/file_level_instructions.jsonl (文件级指令)
- data/processed/file_level_data.jsonl (文件级数据)
- data/processed/step_level_instructions.jsonl (步骤级指令)
- data/processed/step_level_data.jsonl (步骤级数据)
- data/processed/parsed_workflows.jsonl (完整工作流)

输出:
- data/training/training_data_combined.json (组合的完整训练数据)

使用:
    python scripts/02_prepare_training_data.py
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TrainingDataPreparer:
    """准备训练数据"""
    
    def __init__(self):
        self.processed_dir = Path("data/processed")
        self.output_dir = self.processed_dir  # 直接输出到 processed 目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_jsonl(self, filepath: str) -> Dict[str, Any]:
        """加载JSONL文件并按file_id索引"""
        data = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    if 'file_id' in item:
                        file_id = item['file_id']
                        if file_id not in data:
                            data[file_id] = []
                        data[file_id].append(item)
        return data
    
    def load_parsed_workflows(self, filepath: str) -> Dict[str, Any]:
        """加载解析后的工作流"""
        workflows = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    workflow = json.loads(line)
                    workflows[workflow['file_id']] = workflow
        return workflows
    
    def prepare_combined_training_data(self) -> List[Dict[str, Any]]:
        """
        准备组合的训练数据
        为每个步骤创建训练样本，包含指令、上下文和期望输出
        """
        logger.info("加载数据...")
        
        # 加载所有数据
        file_instructions_list = []
        with open(self.processed_dir / "file_level_instructions.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    file_instructions_list.append(json.loads(line))
        
        step_instructions_list = []
        with open(self.processed_dir / "step_level_instructions.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    step_instructions_list.append(json.loads(line))
        
        workflows = {}
        with open(self.processed_dir / "parsed_workflows.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    workflow = json.loads(line)
                    workflows[workflow['file_id']] = workflow
        
        # 按file_id和step_index组织step指令
        step_instr_dict = {}
        for item in step_instructions_list:
            key = (item['file_id'], item['step_index'])
            step_instr_dict[key] = item['instruction']
        
        # 按file_id组织file指令
        file_instr_dict = {}
        for item in file_instructions_list:
            file_instr_dict[item['file_id']] = item['instruction']
        
        # 生成训练样本
        training_data = []
        
        logger.info("生成训练样本...")
        
        for file_id, workflow in workflows.items():
            if file_id not in file_instr_dict:
                continue
            
            file_instruction = file_instr_dict[file_id]
            total_steps = len(workflow['steps'])
            
            # 创建文件级样本（可选）
            # 输入: 文件级指令
            # 输出: 期望生成的步骤指令列表
            
            # 为每个步骤创建训练样本
            for step_idx, step in enumerate(workflow['steps']):
                key = (file_id, step_idx)
                if key not in step_instr_dict:
                    continue
                
                step_instruction = step_instr_dict[key]
                
                # 构建训练样本（指令+输出格式）
                sample = {
                    "file_id": file_id,
                    "step_index": step_idx,
                    "instruction": step_instruction,
                    "input": f"File task: {file_instruction}",  # 可选的上下文信息
                    "output": json.dumps(step, ensure_ascii=False, indent=2),  # 期望的JSON输出
                    "metadata": {
                        "file_instruction": file_instruction,
                        "method": step.get('method', ''),
                        "object": step.get('object', ''),
                    }
                }
                training_data.append(sample)
        
        logger.info(f"生成了 {len(training_data)} 个训练样本")
        return training_data
    
    def save_training_data(self, training_data: List[Dict[str, Any]]):
        """保存训练数据"""
        output_file = self.output_dir / "training_data_combined.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"已保存训练数据到 {output_file}")
        
        # 显示统计信息
        print("\n" + "=" * 80)
        print("📊 训练数据统计")
        print("=" * 80)
        print(f"总样本数: {len(training_data)}")
        
        if training_data:
            print(f"\n📌 样本示例:")
            sample = training_data[0]
            print(f"  File ID: {sample['file_id']}")
            print(f"  Step Index: {sample['step_index']}")
            print(f"  Instruction: {sample['instruction']}")
            print(f"  Input: {sample['input']}")


def main():
    """主函数"""
    print("=" * 80)
    print("📋 Step 2: 准备训练数据")
    print("=" * 80)
    
    preparer = TrainingDataPreparer()
    training_data = preparer.prepare_combined_training_data()
    preparer.save_training_data(training_data)
    
    print("\n✅ 训练数据准备完成！")
    print("下一步: python scripts/03_split_training_data.py")


if __name__ == "__main__":
    main()
