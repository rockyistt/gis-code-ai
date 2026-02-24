#!/usr/bin/env python3
"""
Step 2 增强版: 准备多层次训练数据，充分利用指令权重和同义词信息

核心思想：
1. 双层指令映射：文件级→步骤级
2. 成分权重标注：为Object/Method/Params标注不同权重
3. 同义词扩展：增强输入多样性

生成三种训练样本类型：
- Type A: 步骤级指令→JSON（基础，覆盖率最高）
- Type B: 文件级指令→步骤序列列表（低频，用于约束学习）
- Type C: 带权重的指令→加权JSON（用于难点学习）

输入:
- file_level_instructions.jsonl
- step_level_instructions.jsonl
- parsed_workflows.jsonl
- (可选) component_weights.json - 成分权重
- (可选) synonyms.json - 同义词表

输出:
- training_samples_hierarchical.jsonl - 多层次训练样本
- component_weights_summary.json - 权重统计
- training_stats.json - 样本统计
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class ComponentWeight:
    """成分权重定义"""
    object_weight: float = 1.0  # Object识别难度（通常最高）
    method_weight: float = 0.8  # Method识别难度
    param_weight: float = 0.5   # Parameter提取难度


class SynonymManager:
    """管理同义词转换"""
    
    # 默认同义词库（可扩展）
    DEFAULT_SYNONYMS = {
        "Create": ["Add", "New", "Generate", "Insert", "Make"],
        "Update": ["Modify", "Change", "Edit", "Save", "Set"],
        "Delete": ["Remove", "Drop", "Clear", "Unset"],
        "Open": ["View", "Display", "Show", "Access"],
        "Close": ["Exit", "End", "Finish", "Complete"],
        "Select": ["Pick", "Choose", "Mark", "Highlight"],
        "Click": ["Press", "Tap", "Activate"],
        "Verify": ["Check", "Validate", "Confirm", "Assert"],
    }
    
    def __init__(self, synonyms_file: Optional[str] = None):
        """
        初始化同义词管理器
        
        Args:
            synonyms_file: 自定义同义词JSON文件
        """
        self.synonyms = self.DEFAULT_SYNONYMS.copy()
        
        # 如果提供了自定义同义词，加载它们
        if synonyms_file and Path(synonyms_file).exists():
            try:
                with open(synonyms_file, 'r', encoding='utf-8') as f:
                    custom = json.load(f)
                    self.synonyms.update(custom)
                    logger.info(f"加载自定义同义词: {len(custom)} 个词条")
            except Exception as e:
                logger.warning(f"加载同义词文件失败: {e}")
    
    def get_synonyms(self, word: str) -> List[str]:
        """获取某个词的同义词"""
        # 区分大小写查找
        for key, values in self.synonyms.items():
            if key.lower() == word.lower():
                return [key] + values  # 包含原词
        return [word]


class ComponentWeightCalculator:
    """计算成分权重"""
    
    def __init__(self, weights_file: Optional[str] = None):
        """
        初始化权重计算器
        
        Args:
            weights_file: 预计算的权重JSON文件
        """
        self.weights_file = weights_file
        self.object_frequencies = Counter()  # 对象出现频率
        self.method_frequencies = Counter()  # 方法出现频率
        self.param_frequencies = Counter()   # 参数出现频率
    
    def analyze_workflows(self, workflows: List[Dict]):
        """分析工作流计算频率（用于权重反向）"""
        for workflow in workflows:
            for step in workflow.get('steps', []):
                obj = step.get('object', '').strip()
                method = step.get('method', '').strip()
                
                if obj:
                    self.object_frequencies[obj] += 1
                if method:
                    self.method_frequencies[method] += 1
                
                # 统计参数
                for param in step.get('parameters', []):
                    param_name = param.get('name', '')
                    if param_name:
                        self.param_frequencies[param_name] += 1
    
    def calculate_weight(self, component_type: str, component_value: str) -> float:
        """
        计算单个成分的权重（频率越低，权重越高 - 越罕见越难）
        
        Args:
            component_type: 'object', 'method', 或 'parameter'
            component_value: 具体的值
            
        Returns:
            权重值 (0-1 之间)
        """
        if component_type == 'object':
            freq_map = self.object_frequencies
        elif component_type == 'method':
            freq_map = self.method_frequencies
        else:
            freq_map = self.param_frequencies
        
        if not freq_map:
            return 0.5  # 默认中等权重
        
        # 获取此组件的频率
        freq = freq_map.get(component_value, 1)
        max_freq = max(freq_map.values())
        
        # 反向权重：频率越低，权重越高
        # weight = 1 - (freq / max_freq) 
        # 范围: [0, 1)，最常见的权重接近0，最罕见的权重接近1
        weight = 1.0 - (freq / max_freq) if max_freq > 0 else 0.5
        
        # 调整到更有用的范围 [0.5, 1.0]
        weight = 0.5 + weight * 0.5
        return round(weight, 3)


class HierarchicalTrainingDataGenerator:
    """生成多层次训练数据"""
    
    def __init__(self, processed_dir: str = "data/processed"):
        self.processed_dir = Path(processed_dir)
        self.synonym_mgr = SynonymManager()
        self.weight_calc = ComponentWeightCalculator()
        self.samples = []
    
    def load_all_data(self) -> Tuple[Dict, Dict, Dict, List]:
        """加载所有必要的数据"""
        logger.info("加载数据...")
        
        # 加载文件级指令
        file_instr_dict = {}
        with open(self.processed_dir / "file_level_instructions.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    file_instr_dict[item['file_id']] = item['instruction']
        logger.info(f"✓ 文件级指令: {len(file_instr_dict)}")
        
        # 加载步骤级指令
        step_instr_dict = {}
        with open(self.processed_dir / "step_level_instructions.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    key = (item['file_id'], item['step_index'])
                    step_instr_dict[key] = item['instruction']
        logger.info(f"✓ 步骤级指令: {len(step_instr_dict)}")
        
        # 加载工作流
        workflows = []
        with open(self.processed_dir / "parsed_workflows.jsonl", 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    workflows.append(json.loads(line))
        logger.info(f"✓ 工作流: {len(workflows)}")
        
        # 计算权重
        self.weight_calc.analyze_workflows(workflows)
        logger.info(f"✓ 权重计算完成")
        
        return file_instr_dict, step_instr_dict, {w['file_id']: w for w in workflows}, workflows
    
    def generate_type_a_samples(self, 
                               file_id: str, 
                               step_idx: int, 
                               step_instr: str,
                               step: Dict,
                               file_instr: str) -> Dict:
        """
        Type A: 步骤级样本（最基础，最常见）
        
        输入: 步骤级指令 + 文件上下文
        输出: 单个JSON步骤
        
        示例:
        {
            "type": "step_level",
            "instruction": "Step 2/5: Create asset in GIS system",
            "input": "File task: Test workflow in GIS system: Work with Asset through 5 steps",
            "output": {"method": "Create", "object": "Asset", ...},
            "weights": {"object": 0.8, "method": 0.7, "params": 0.5}
        }
        """
        obj = step.get('object', '').strip()
        method = step.get('method', '').strip()
        
        # 计算此步骤各成分的权重
        weights = {
            "object": self.weight_calc.calculate_weight('object', obj) if obj else 0.5,
            "method": self.weight_calc.calculate_weight('method', method) if method else 0.5,
            "params": 0.5  # 参数权重固定
        }
        
        return {
            "type": "step_level",
            "file_id": file_id,
            "step_index": step_idx,
            "instruction": step_instr,
            "input": f"File task: {file_instr}",
            "output": json.dumps(step, ensure_ascii=False),  # 完整JSON
            "weights": weights,
            "difficulty": sum(weights.values()) / len(weights)  # 平均权重作为难度
        }
    
    def generate_type_b_samples(self,
                               file_id: str,
                               file_instr: str,
                               workflow: Dict) -> Optional[Dict]:
        """
        Type B: 文件级样本（低频，用于整体约束）
        
        输入: 文件级指令
        输出: 步骤指令序列或步骤摘要列表
        
        示例:
        {
            "type": "file_level",
            "instruction": "Test workflow: Create Asset in GIS",
            "input": "GIS system, Asset type workflow",
            "output": [
                "Step 1: Open Asset",
                "Step 2: Create Attribute",
                "Step 3: Verify Field"
            ],
            "weights": {"sequence_accuracy": 0.9, "coverage": 0.8}
        }
        """
        steps = workflow.get('steps', [])
        if not steps:
            return None
        
        # 构建步骤摘要列表
        step_summaries = []
        for i, step in enumerate(steps, 1):
            method = step.get('method', '').strip()
            obj = step.get('object', '').strip()
            summary = f"Step {i}: {method} {obj}".strip()
            step_summaries.append(summary)
        
        return {
            "type": "file_level",
            "file_id": file_id,
            "instruction": file_instr,
            "input": f"Workflow with {len(steps)} steps",
            "output": json.dumps(step_summaries, ensure_ascii=False),
            "weights": {
                "sequence_accuracy": 0.85,  # 步骤顺序的重要性
                "coverage": 0.80  # 步骤覆盖的完整性
            },
            "difficulty": 0.7  # 文件级通常是中等难度
        }
    
    def generate_type_c_samples(self,
                               file_id: str,
                               step_idx: int,
                               step_instr: str,
                               step: Dict,
                               file_instr: str,
                               synonym_variant: int = 0) -> Dict:
        """
        Type C: 同义词变体样本（数据增强）
        
        通过使用同义词替换，为同一个步骤生成多个输入变体
        
        示例:
        {
            "type": "synonym_variant",
            "instruction": "Step 2/5: Add asset in GIS system",  # "Create" -> "Add"
            "input": "File task: ...",
            "output": {"method": "Create", "object": "Asset", ...},
            "synonym_info": {"original": "Create", "variant": "Add", "variant_id": 0}
        }
        """
        method = step.get('method', '').strip()
        synonyms = self.synonym_mgr.get_synonyms(method)
        
        if len(synonyms) <= 1:
            return None  # 没有同义词变体
        
        # 获取指定的同义词
        variant_method = synonyms[min(synonym_variant + 1, len(synonyms) - 1)]
        
        # 替换指令中的方法
        modified_instr = step_instr.replace(method, variant_method)
        
        return {
            "type": "synonym_variant",
            "file_id": file_id,
            "step_index": step_idx,
            "instruction": modified_instr,
            "input": f"File task: {file_instr}",
            "output": json.dumps(step, ensure_ascii=False),
            "weights": {
                "synonym_robustness": 0.7,  # 同义词鲁棒性权重
            },
            "synonym_info": {
                "original_method": method,
                "variant_method": variant_method,
                "variant_id": synonym_variant
            },
            "difficulty": 0.75  # 同义词变体中等偏难
        }
    
    def generate_all_samples(self):
        """生成所有类型的样本"""
        logger.info("\n生成训练样本...")
        
        file_instr_dict, step_instr_dict, workflow_dict, workflows_list = self.load_all_data()
        
        sample_count = {"type_a": 0, "type_b": 0, "type_c": 0, "total": 0}
        
        for workflow in workflows_list:
            file_id = workflow['file_id']
            file_instr = file_instr_dict.get(file_id)
            steps = workflow.get('steps', [])
            
            if not file_instr or not steps:
                continue
            
            # ============= Type B: 文件级样本（每个文件一个）=============
            type_b_sample = self.generate_type_b_samples(file_id, file_instr, workflow)
            if type_b_sample:
                self.samples.append(type_b_sample)
                sample_count["type_b"] += 1
                sample_count["total"] += 1
            
            # ============= Type A & C: 步骤级样本 =============
            for step_idx, step in enumerate(steps):
                key = (file_id, step_idx)
                step_instr = step_instr_dict.get(key)
                
                if not step_instr:
                    continue
                
                # Type A: 基础步骤级样本
                type_a_sample = self.generate_type_a_samples(
                    file_id, step_idx, step_instr, step, file_instr
                )
                self.samples.append(type_a_sample)
                sample_count["type_a"] += 1
                sample_count["total"] += 1
                
                # Type C: 同义词变体（每个步骤最多2个变体）
                method = step.get('method', '').strip()
                synonyms = self.synonym_mgr.get_synonyms(method)
                
                for variant_id in range(min(2, len(synonyms) - 1)):
                    type_c_sample = self.generate_type_c_samples(
                        file_id, step_idx, step_instr, step, file_instr, variant_id
                    )
                    if type_c_sample:
                        self.samples.append(type_c_sample)
                        sample_count["type_c"] += 1
                        sample_count["total"] += 1
        
        logger.info(f"✓ 样本生成完成:")
        logger.info(f"  - Type A (步骤级): {sample_count['type_a']}")
        logger.info(f"  - Type B (文件级): {sample_count['type_b']}")
        logger.info(f"  - Type C (同义词): {sample_count['type_c']}")
        logger.info(f"  - 总计: {sample_count['total']}")
        
        return sample_count
    
    def save_samples(self):
        """保存所有样本"""
        output_file = self.processed_dir / "training_samples_hierarchical.jsonl"
        logger.info(f"\n保存样本到 {output_file}...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for sample in self.samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info(f"✓ 已保存 {len(self.samples)} 个样本")
        
        # 保存统计信息
        stats = {
            "total_samples": len(self.samples),
            "type_a_count": sum(1 for s in self.samples if s.get('type') == 'step_level'),
            "type_b_count": sum(1 for s in self.samples if s.get('type') == 'file_level'),
            "type_c_count": sum(1 for s in self.samples if s.get('type') == 'synonym_variant'),
            "avg_difficulty": sum(s.get('difficulty', 0.5) for s in self.samples) / len(self.samples) if self.samples else 0,
        }
        
        stats_file = self.processed_dir / "training_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 统计信息已保存: {stats_file}")
        print("\n" + "=" * 80)
        print(f"📊 训练数据统计:")
        print(f"  总样本数: {stats['total_samples']}")
        print(f"  Type A (步骤级): {stats['type_a_count']}")
        print(f"  Type B (文件级): {stats['type_b_count']}")
        print(f"  Type C (同义词): {stats['type_c_count']}")
        print(f"  平均难度: {stats['avg_difficulty']:.2f}")
        print("=" * 80)


def main():
    """主函数"""
    print("=" * 80)
    print("📋 Step 2 增强: 多层次训练数据生成")
    print("=" * 80)
    print("\n本脚本将生成三类训练样本:")
    print("  Type A: 步骤级指令→JSON（基础）")
    print("  Type B: 文件级指令→步骤序列（约束学习）")
    print("  Type C: 同义词变体（数据增强）")
    print("\n每个样本都包含权重信息，可用于难点学习")
    print("=" * 80)
    
    generator = HierarchicalTrainingDataGenerator()
    sample_count = generator.generate_all_samples()
    generator.save_samples()
    
    print("\n✅ 增强的多层次训练数据生成完成！")
    print("下一步选择:")
    print("  选项1: 使用本脚本输出 (hierarchical) 进行训练")
    print("  选项2: 运行 03_split_training_data.py 处理原始格式")


if __name__ == "__main__":
    main()
