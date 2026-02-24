#!/usr/bin/env python3
"""
Step 0: Parse flat GIS test JSON files into structured workflow format.

输入: data/raw/ 目录下的所有JSON文件
输出: data/processed/parsed_workflows.jsonl (结构化的工作流JSONL文件)

使用:
    python scripts/00_parse_workflows.py
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WorkflowParser:
    """解析扁平化的JSON结构为结构化工作流"""
    
    def __init__(self, raw_data_dir: str):
        """
        Args:
            raw_data_dir: 包含原始JSON文件的目录
        """
        self.raw_data_dir = Path(raw_data_dir)
        self.file_counter = 0  # 用于生成顺序编号
        
    def parse_file(self, json_path: Path) -> Dict[str, Any]:
        """
        解析单个JSON文件为结构化格式
        
        Args:
            json_path: JSON文件路径
            
        Returns:
            结构化的工作流字典
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 提取元数据
        total_steps_raw = data.get("teststeps0", [0])
        if total_steps_raw and len(total_steps_raw) > 0:
            try:
                total_steps = int(total_steps_raw[0]) if isinstance(total_steps_raw[0], (str, int)) else 0
            except (ValueError, TypeError):
                total_steps = 0
        else:
            total_steps = 0
        
        # 生成顺序file_id (file_000001, file_000002, 等)
        self.file_counter += 1
        file_id = f"file_{self.file_counter:06d}"
        
        workflow = {
            "file_id": file_id,
            "test_env": data.get("testenvs0", ["Unknown"])[0] if data.get("testenvs0") else "Unknown",
            "test_app": data.get("testapps0", ["Unknown"])[0] if data.get("testapps0") else "Unknown",
            "total_steps": total_steps,
            "test_cases": data.get("testcases", []),
            "steps": []
        }
        
        # 解析步骤
        total_steps = workflow["total_steps"]
        for step_idx in range(total_steps):
            step = self._parse_step(data, step_idx)
            if step:
                workflow["steps"].append(step)
        
        return workflow
    
    def _parse_step(self, data: Dict, step_idx: int) -> Dict[str, Any]:
        """解析扁平结构中的单个步骤"""
        suffix = f"0_{step_idx}"
        
        step = {
            "step_index": step_idx,
            "database": data.get(f"testdbs{suffix}", ""),
            "object": data.get(f"testobjs{suffix}", ""),
            "object_id": data.get(f"testobj_ids{suffix}", ""),
            "module": data.get(f"testmodules{suffix}", ""),
            "method": data.get(f"testmethodes{suffix}", ""),
            "command": data.get(f"testcommands{suffix}", ""),
            "test_data": {
                "create": data.get(f"testdata_cr{suffix}", {}),
                "update": data.get(f"testdata_upd{suffix}", {}),
                "editor": data.get(f"testdata_editor{suffix}", {})
            }
        }
        
        return step
    
    def parse_all(self, output_path: str) -> List[Dict[str, Any]]:
        """
        解析raw_data_dir中的所有JSON文件
        
        Args:
            output_path: 解析后的工作流保存路径 (JSONL格式)
            
        Returns:
            解析后的工作流列表
        """
        workflows = []
        json_files = list(self.raw_data_dir.rglob("*.json"))
        
        logger.info(f"找到 {len(json_files)} 个JSON文件")
        
        for json_path in json_files:
            try:
                workflow = self.parse_file(json_path)
                workflows.append(workflow)
                logger.info(f"✓ 已解析: {json_path.name} ({workflow['total_steps']} 步骤)")
            except Exception as e:
                logger.error(f"✗ 解析失败 {json_path}: {e}")
        
        # 保存为JSONL
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for workflow in workflows:
                f.write(json.dumps(workflow, ensure_ascii=False) + '\n')
        
        logger.info(f"已保存 {len(workflows)} 个工作流到 {output_path}")
        
        return workflows


def main():
    """主函数"""
    print("=" * 80)
    print("📋 Step 0: 解析原始JSON文件")
    print("=" * 80)
    
    parser = WorkflowParser(raw_data_dir="data/raw")
    workflows = parser.parse_all(output_path="data/processed/parsed_workflows.jsonl")
    
    # 显示样本
    print("\n" + "=" * 80)
    print("📌 样本工作流")
    print("=" * 80)
    
    if workflows:
        sample = workflows[0]
        print(f"\n文件ID: {sample['file_id']}")
        print(f"应用: {sample['test_app']}")
        print(f"环境: {sample['test_env']}")
        print(f"步骤总数: {sample['total_steps']}")
        if sample['steps']:
            print(f"\n第一个步骤: {sample['steps'][0]['module']} - {sample['steps'][0]['method']}")
    
    print("\n✅ 解析完成！")
    print(f"输出文件: data/processed/parsed_workflows.jsonl")


if __name__ == "__main__":
    main()
