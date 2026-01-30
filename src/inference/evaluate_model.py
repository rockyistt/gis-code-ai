"""
模型评估脚本 - 在测试集上评估CodeLlama微调模型的性能
"""

import json
import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
from tqdm import tqdm
import re

# 假设已有load_model模块
try:
    from src.inference.load_model import GISCodeGenerator
except ImportError:
    print("⚠️ 无法导入load_model，请检查路径")


class WorkflowEvaluator:
    """工作流生成评估器"""
    
    @staticmethod
    def is_valid_json(text: str) -> bool:
        """检查是否为有效JSON"""
        try:
            json.loads(text)
            return True
        except:
            return False
    
    @staticmethod
    def extract_json(text: str) -> Dict:
        """从文本中提取JSON"""
        try:
            # 尝试直接解析
            return json.loads(text)
        except:
            # 尝试找到第一个{和最后一个}
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end+1])
                except:
                    pass
            return None
    
    @staticmethod
    def structure_match(generated: Dict, reference: Dict) -> float:
        """
        计算结构匹配度 (0-1)
        检查必要字段是否存在
        """
        if not isinstance(generated, dict):
            return 0.0
        
        required_fields = ["workflow"]
        if not all(field in generated for field in required_fields):
            return 0.0
        
        workflow = generated.get("workflow", {})
        ref_workflow = reference.get("workflow", {})
        
        # 检查steps
        gen_steps = workflow.get("steps", [])
        ref_steps = ref_workflow.get("steps", [])
        
        if len(gen_steps) == 0:
            return 0.0
        
        # 检查每个step的必要字段
        required_step_fields = ["module", "method", "object", "database"]
        valid_steps = 0
        
        for step in gen_steps:
            if all(field in step for field in required_step_fields):
                valid_steps += 1
        
        structure_score = valid_steps / len(gen_steps) if gen_steps else 0.0
        
        # 步骤数接近度
        if ref_steps:
            length_ratio = min(len(gen_steps), len(ref_steps)) / max(len(gen_steps), len(ref_steps))
            structure_score = 0.7 * structure_score + 0.3 * length_ratio
        
        return structure_score
    
    @staticmethod
    def semantic_similarity(text1: str, text2: str) -> float:
        """
        简单的语义相似度 (基于关键词匹配)
        更好的方法是使用Sentence-BERT
        """
        # 提取关键词
        def extract_keywords(text):
            # 移除标点和特殊字符
            text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
            words = set(text.split())
            # 过滤短词
            return {w for w in words if len(w) > 2}
        
        kw1 = extract_keywords(text1)
        kw2 = extract_keywords(text2)
        
        if not kw1 or not kw2:
            return 0.0
        
        intersection = len(kw1 & kw2)
        union = len(kw1 | kw2)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def evaluate_sample(
        instruction: str,
        generated_output: str,
        reference_output: str,
    ) -> Dict[str, float]:
        """
        评估单个样本
        
        Returns:
            包含多个指标的字典
        """
        metrics = {}
        
        # 1. JSON有效性
        generated_json = WorkflowEvaluator.extract_json(generated_output)
        reference_json = WorkflowEvaluator.extract_json(reference_output)
        
        metrics["json_valid"] = 1.0 if generated_json else 0.0
        
        # 2. 结构匹配度
        if generated_json and reference_json:
            metrics["structure_match"] = WorkflowEvaluator.structure_match(
                generated_json, reference_json
            )
        else:
            metrics["structure_match"] = 0.0
        
        # 3. 语义相似度
        metrics["semantic_similarity"] = WorkflowEvaluator.semantic_similarity(
            generated_output, reference_output
        )
        
        # 4. 步骤数对比
        if generated_json and reference_json:
            gen_steps = len(generated_json.get("workflow", {}).get("steps", []))
            ref_steps = len(reference_json.get("workflow", {}).get("steps", []))
            
            if ref_steps > 0:
                metrics["step_count_ratio"] = min(gen_steps, ref_steps) / ref_steps
            else:
                metrics["step_count_ratio"] = 1.0 if gen_steps == 0 else 0.0
        else:
            metrics["step_count_ratio"] = 0.0
        
        return metrics


class ModelEvaluator:
    """模型评估框架"""
    
    def __init__(self, model: GISCodeGenerator):
        self.model = model
        self.evaluator = WorkflowEvaluator()
    
    def evaluate_on_dataset(
        self,
        test_data: List[Dict],
        num_samples: int = None,
        output_file: str = None,
    ) -> Dict[str, Any]:
        """
        在测试集上评估模型
        
        Args:
            test_data: 测试样本列表，每个包含instruction, input, output
            num_samples: 评估样本数 (None=全部)
            output_file: 保存详细结果的文件
        
        Returns:
            评估结果字典
        """
        
        if num_samples is None:
            num_samples = len(test_data)
        
        num_samples = min(num_samples, len(test_data))
        
        print(f"\n{'='*70}")
        print(f"🧪 开始评估模型")
        print(f"{'='*70}")
        print(f"📊 测试样本数: {num_samples}")
        
        all_metrics = []
        detailed_results = []
        
        for i, sample in enumerate(tqdm(test_data[:num_samples], desc="评估进度")):
            instruction = sample.get("instruction", "")
            context = sample.get("input", "")
            reference_output = sample.get("output", "")
            
            try:
                # 生成代码
                result = self.model.generate(instruction, context)
                generated_output = result.get("generated_code", "")
                
                # 评估
                metrics = self.evaluator.evaluate_sample(
                    instruction, generated_output, reference_output
                )
                
                all_metrics.append(metrics)
                
                # 记录详细结果
                detailed_results.append({
                    "sample_id": i,
                    "instruction": instruction,
                    "context": context,
                    "generated_output": generated_output,
                    "reference_output": reference_output,
                    "metrics": metrics
                })
                
            except Exception as e:
                print(f"❌ 样本{i}评估失败: {str(e)}")
                all_metrics.append({
                    "json_valid": 0.0,
                    "structure_match": 0.0,
                    "semantic_similarity": 0.0,
                    "step_count_ratio": 0.0,
                    "error": str(e)
                })
        
        # 计算平均指标
        summary = {}
        if all_metrics:
            for key in ["json_valid", "structure_match", "semantic_similarity", "step_count_ratio"]:
                values = [m.get(key, 0.0) for m in all_metrics if "error" not in m]
                if values:
                    summary[key] = {
                        "mean": np.mean(values),
                        "std": np.std(values),
                        "min": np.min(values),
                        "max": np.max(values),
                    }
        
        # 计算综合评分 (加权平均)
        if all_metrics:
            json_valid_scores = [m.get("json_valid", 0) for m in all_metrics if "error" not in m]
            structure_scores = [m.get("structure_match", 0) for m in all_metrics if "error" not in m]
            semantic_scores = [m.get("semantic_similarity", 0) for m in all_metrics if "error" not in m]
            
            if json_valid_scores:
                overall_score = (
                    0.3 * np.mean(json_valid_scores) +  # JSON有效性权重30%
                    0.5 * np.mean(structure_scores) +   # 结构匹配权重50%
                    0.2 * np.mean(semantic_scores)      # 语义相似权重20%
                )
                summary["overall_score"] = overall_score
        
        # 保存详细结果
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "summary": summary,
                    "detailed_results": detailed_results
                }, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 详细结果已保存: {output_file}")
        
        return {
            "summary": summary,
            "num_samples": num_samples,
            "detailed_results": detailed_results
        }
    
    def print_summary(self, results: Dict):
        """打印评估摘要"""
        
        summary = results["summary"]
        num_samples = results["num_samples"]
        
        print(f"\n{'='*70}")
        print(f"📊 评估结果摘要 (样本数: {num_samples})")
        print(f"{'='*70}")
        
        # JSON有效性
        if "json_valid" in summary:
            stat = summary["json_valid"]
            print(f"\n✅ JSON有效性:")
            print(f"  平均: {stat['mean']:.2%}")
            print(f"  范围: [{stat['min']:.2%}, {stat['max']:.2%}]")
        
        # 结构匹配度
        if "structure_match" in summary:
            stat = summary["structure_match"]
            print(f"\n🏗️ 结构匹配度:")
            print(f"  平均: {stat['mean']:.2%}")
            print(f"  标准差: {stat['std']:.2%}")
            print(f"  范围: [{stat['min']:.2%}, {stat['max']:.2%}]")
        
        # 语义相似度
        if "semantic_similarity" in summary:
            stat = summary["semantic_similarity"]
            print(f"\n📝  语义相似度:")
            print(f"  平均: {stat['mean']:.2%}")
            print(f"  标准差: {stat['std']:.2%}")
            print(f"  范围: [{stat['min']:.2%}, {stat['max']:.2%}]")
        
        # 步骤数对比
        if "step_count_ratio" in summary:
            stat = summary["step_count_ratio"]
            print(f"\n📍 步骤数对比:")
            print(f"  平均比: {stat['mean']:.2%}")
            print(f"  范围: [{stat['min']:.2%}, {stat['max']:.2%}]")
        
        # 综合评分
        if "overall_score" in summary:
            score = summary["overall_score"]
            print(f"\n🎯 综合评分:")
            print(f"  {score:.2%}")
            
            if score > 0.8:
                print(f"  等级: ⭐⭐⭐⭐⭐ 优秀")
            elif score > 0.6:
                print(f"  等级: ⭐⭐⭐⭐ 良好")
            elif score > 0.4:
                print(f"  等级: ⭐⭐⭐ 中等")
            else:
                print(f"  等级: ⭐⭐ 需要改进")
        
        print(f"\n{'='*70}\n")


if __name__ == "__main__":
    # 使用示例
    import sys
    
    model_path = sys.argv[1] if len(sys.argv) > 1 else "/content/drive/MyDrive/gis-models/codellama-gis-lora"
    test_data_path = sys.argv[2] if len(sys.argv) > 2 else "data/training/training_data_val.json"
    
    print(f"📦 加载模型: {model_path}")
    generator = GISCodeGenerator(model_path)
    
    print(f"📂 加载测试数据: {test_data_path}")
    with open(test_data_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    # 创建评估器
    evaluator = ModelEvaluator(generator)
    
    # 评估 (使用前100个样本快速测试)
    results = evaluator.evaluate_on_dataset(
        test_data,
        num_samples=100,
        output_file="data/evaluation/model_evaluation_results.json"
    )
    
    # 打印摘要
    evaluator.print_summary(results)
