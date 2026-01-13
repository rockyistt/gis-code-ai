"""
指令生成方法评估系统

评估三种不需要API的方法：
1. 基础规则模板
2. 改进规则模板（增强版）
3. 本地小型模型（可选，需要下载）

评估指标：
- 自动化指标：相似度、BLEU、ROUGE
- 质量指标：完整性、准确性、可读性
- 效率指标：速度、资源占用
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics


# ============================================================
# 评估指标定义
# ============================================================

class EvaluationMetrics:
    """评估指标计算"""
    
    @staticmethod
    def word_overlap_score(generated: str, reference: str) -> float:
        """词重叠率 - 简单但有效的指标"""
        gen_words = set(generated.lower().split())
        ref_words = set(reference.lower().split())
        
        if not ref_words:
            return 0.0
        
        overlap = len(gen_words & ref_words)
        return overlap / len(ref_words)
    
    @staticmethod
    def length_ratio_score(generated: str, reference: str) -> float:
        """长度比例 - 评估生成长度是否合理"""
        gen_len = len(generated.split())
        ref_len = len(reference.split())
        
        if ref_len == 0:
            return 0.0
        
        ratio = gen_len / ref_len
        # 理想比例在0.8-1.2之间
        if 0.8 <= ratio <= 1.2:
            return 1.0
        elif 0.6 <= ratio <= 1.5:
            return 0.8
        else:
            return 0.5
    
    @staticmethod
    def keyword_coverage_score(generated: str, keywords: List[str]) -> float:
        """关键词覆盖率"""
        generated_lower = generated.lower()
        covered = sum(1 for kw in keywords if kw.lower() in generated_lower)
        
        if not keywords:
            return 1.0
        
        return covered / len(keywords)
    
    @staticmethod
    def completeness_score(generated: str) -> float:
        """完整性评分 - 检查生成的指令是否完整"""
        score = 0.0
        
        # 1. 长度合理 (10-200词)
        word_count = len(generated.split())
        if 10 <= word_count <= 200:
            score += 0.3
        elif 5 <= word_count <= 250:
            score += 0.15
        
        # 2. 包含动词（动作）
        action_verbs = ['create', 'open', 'update', 'delete', 'select', 'click', 
                       'verify', 'switch', 'navigate', 'perform', 'set', 'add']
        if any(verb in generated.lower() for verb in action_verbs):
            score += 0.3
        
        # 3. 包含对象
        if any(c.isupper() for c in generated):  # 包含大写字母（通常是对象名）
            score += 0.2
        
        # 4. 语法结构（简单检查）
        if generated[0].isupper() and not generated.endswith('...'):
            score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def readability_score(generated: str) -> float:
        """可读性评分"""
        score = 1.0
        
        # 惩罚因素
        # 1. 过长的句子
        if len(generated) > 300:
            score -= 0.2
        
        # 2. 包含技术细节过多
        tech_patterns = ['FLD_CSTM', 'gis_program_manager', 'predicate.eq']
        if any(pattern in generated for pattern in tech_patterns):
            score -= 0.3
        
        # 3. 包含原始字段名
        if '{' in generated or '}' in generated:
            score -= 0.2
        
        # 4. 重复词过多
        words = generated.lower().split()
        if len(words) > 0:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.5:
                score -= 0.2
        
        return max(score, 0.0)
    
    @staticmethod
    def calculate_bleu(generated: str, reference: str) -> float:
        """简化的BLEU分数（1-gram和2-gram）"""
        gen_words = generated.lower().split()
        ref_words = reference.lower().split()
        
        if not gen_words or not ref_words:
            return 0.0
        
        # 1-gram precision
        gen_1gram = set(gen_words)
        ref_1gram = set(ref_words)
        precision_1 = len(gen_1gram & ref_1gram) / len(gen_1gram) if gen_1gram else 0
        
        # 2-gram precision
        gen_2gram = set(zip(gen_words[:-1], gen_words[1:]))
        ref_2gram = set(zip(ref_words[:-1], ref_words[1:]))
        precision_2 = len(gen_2gram & ref_2gram) / len(gen_2gram) if gen_2gram else 0
        
        # 组合分数
        bleu = (precision_1 + precision_2) / 2
        
        # 长度惩罚
        length_penalty = min(len(gen_words) / len(ref_words), 1.0) if ref_words else 0
        
        return bleu * length_penalty


# ============================================================
# 评估器
# ============================================================

class MethodEvaluator:
    """方法评估器"""
    
    def __init__(self):
        self.metrics = EvaluationMetrics()
        self.results = defaultdict(list)
    
    def extract_key_info(self, step: Dict) -> Dict[str, Any]:
        """提取步骤的关键信息用于评估"""
        return {
            "module": step.get("module", ""),
            "method": step.get("method", ""),
            "object": step.get("object", ""),
            "database": step.get("database", ""),
        }
    
    def create_reference_instruction(self, step: Dict) -> str:
        """创建参考指令（用于对比）"""
        key_info = self.extract_key_info(step)
        
        # 简单的参考指令模板
        templates = {
            "Create": f"Create {key_info['object']} object",
            "Update": f"Update {key_info['object']} object", 
            "Delete": f"Delete {key_info['object']} object",
            "Open Object": f"Open {key_info['object']} in editor",
            "Select Tab": f"Select {key_info['object']} tab",
        }
        
        return templates.get(key_info['method'], 
                           f"{key_info['method']} {key_info['object']}")
    
    def evaluate_single(self, generated: str, step: Dict, 
                       method_name: str) -> Dict[str, float]:
        """评估单个生成结果"""
        reference = self.create_reference_instruction(step)
        key_info = self.extract_key_info(step)
        
        # 提取关键词
        keywords = [
            key_info['method'],
            key_info['object'],
            key_info['module']
        ]
        keywords = [k for k in keywords if k]
        
        # 计算各项指标
        scores = {
            "word_overlap": self.metrics.word_overlap_score(generated, reference),
            "length_ratio": self.metrics.length_ratio_score(generated, reference),
            "keyword_coverage": self.metrics.keyword_coverage_score(generated, keywords),
            "completeness": self.metrics.completeness_score(generated),
            "readability": self.metrics.readability_score(generated),
            "bleu": self.metrics.calculate_bleu(generated, reference)
        }
        
        # 综合评分
        scores["overall"] = (
            scores["word_overlap"] * 0.2 +
            scores["keyword_coverage"] * 0.25 +
            scores["completeness"] * 0.25 +
            scores["readability"] * 0.15 +
            scores["bleu"] * 0.15
        )
        
        # 保存结果
        self.results[method_name].append(scores)
        
        return scores
    
    def evaluate_method(self, inferencer, steps: List[Dict], 
                       method_name: str) -> Dict[str, Any]:
        """评估一个方法在所有步骤上的表现"""
        print(f"\n评估方法: {method_name}")
        print("-" * 60)
        
        all_scores = []
        start_time = time.time()
        
        for i, step in enumerate(steps):
            if (i + 1) % 100 == 0:
                print(f"  进度: {i + 1}/{len(steps)}")
            
            try:
                # 生成指令
                generated = inferencer.infer_step_instruction(step)
                
                # 评估
                scores = self.evaluate_single(generated, step, method_name)
                all_scores.append(scores)
                
            except Exception as e:
                print(f"  ⚠️  步骤 {i} 失败: {e}")
                continue
        
        elapsed_time = time.time() - start_time
        
        # 计算统计信息
        summary = self.calculate_summary(all_scores, elapsed_time, len(steps))
        
        return summary
    
    def calculate_summary(self, all_scores: List[Dict[str, float]], 
                         elapsed_time: float, total_steps: int) -> Dict[str, Any]:
        """计算汇总统计"""
        if not all_scores:
            return {"error": "No valid scores"}
        
        summary = {
            "total_steps": total_steps,
            "successful_steps": len(all_scores),
            "elapsed_time": elapsed_time,
            "steps_per_second": len(all_scores) / elapsed_time if elapsed_time > 0 else 0,
        }
        
        # 计算每个指标的统计
        for metric in all_scores[0].keys():
            values = [s[metric] for s in all_scores]
            summary[metric] = {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values),
                "max": max(values)
            }
        
        return summary
    
    def compare_methods(self, summaries: Dict[str, Dict]) -> str:
        """生成方法对比报告"""
        report = [
            "\n" + "="*70,
            "方法对比报告",
            "="*70,
        ]
        
        # 提取关键指标
        metrics_to_compare = ["overall", "completeness", "readability", "keyword_coverage"]
        
        report.append("\n📊 核心指标对比:")
        report.append("-" * 70)
        
        # 表头
        header = f"{'指标':<20} " + " ".join(f"{name:>15}" for name in summaries.keys())
        report.append(header)
        report.append("-" * 70)
        
        # 各指标对比
        for metric in metrics_to_compare:
            values = []
            for method_name, summary in summaries.items():
                if metric in summary and "mean" in summary[metric]:
                    values.append(f"{summary[metric]['mean']:.3f}")
                else:
                    values.append("N/A")
            
            row = f"{metric:<20} " + " ".join(f"{v:>15}" for v in values)
            report.append(row)
        
        # 性能对比
        report.append("\n⚡ 性能对比:")
        report.append("-" * 70)
        
        for method_name, summary in summaries.items():
            sps = summary.get('steps_per_second', 0)
            time = summary.get('elapsed_time', 0)
            report.append(f"{method_name:<20} {sps:>10.1f} steps/sec  ({time:.2f}s total)")
        
        # 推荐
        report.append("\n🏆 推荐:")
        report.append("-" * 70)
        
        # 找出最佳方法
        best_overall = max(summaries.items(), 
                          key=lambda x: x[1].get('overall', {}).get('mean', 0))
        fastest = max(summaries.items(),
                     key=lambda x: x[1].get('steps_per_second', 0))
        
        report.append(f"最佳质量: {best_overall[0]} "
                     f"(综合评分: {best_overall[1]['overall']['mean']:.3f})")
        report.append(f"最快速度: {fastest[0]} "
                     f"({fastest[1]['steps_per_second']:.1f} steps/sec)")
        
        return "\n".join(report)
    
    def save_detailed_results(self, output_file: str):
        """保存详细评估结果"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(dict(self.results), f, indent=2, ensure_ascii=False)
        print(f"\n💾 详细结果已保存: {output_file}")


# ============================================================
# 三种方法的实现
# ============================================================

class Method1_BasicRules:
    """方法1: 基础规则模板"""
    
    def __init__(self):
        self.templates = {
            "Create": "Create {object}",
            "Update": "Update {object}",
            "Delete": "Delete {object}",
            "Open Object": "Open {object}",
            "Select Tab": "Select {object} tab",
            "Click Oneshot Button": "Click {object} button",
        }
    
    def infer_step_instruction(self, step: Dict) -> str:
        method = step.get('method', '')
        obj = step.get('object', '')
        
        template = self.templates.get(method, "{method} {object}")
        return template.format(method=method, object=obj)


class Method2_EnhancedRules:
    """方法2: 增强规则模板（更详细的规则）"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create a new",
            "Update": "Update the existing",
            "Delete": "Delete the",
            "Open Object": "Open",
            "Open Object with ID": "Open",
            "Switch Spatial Context": "Switch to",
            "Verify Field": "Verify",
            "Select Tab": "Navigate to the",
            "Click Oneshot Button": "Click the",
            "Select first HV object": "Select the first",
            "Select second HV object": "Select the second",
            "Datamodel Check": "Perform consistency check on"
        }
    
    def clean_object_name(self, obj: str) -> str:
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def extract_attributes_count(self, step: Dict) -> int:
        """提取属性数量"""
        test_data = step.get('test_data', {})
        for section in ['create', 'update']:
            if section in test_data and test_data[section]:
                data = test_data[section]
                for key, value in data.items():
                    if key.startswith('FLD_CSTM') and isinstance(value, dict):
                        return len([k for k in value.keys() if k != 'ID'])
        return 0
    
    def infer_step_instruction(self, step: Dict) -> str:
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        
        action = self.action_verbs.get(method, method)
        
        # 根据方法类型生成更详细的描述
        if method == "Create":
            attr_count = self.extract_attributes_count(step)
            if attr_count > 0:
                return f"{action} {obj} object with {attr_count} specified attributes in {database}"
            return f"{action} {obj} object in {database}"
        
        elif method in ["Open Object", "Open Object with ID"]:
            return f"{action} {obj} object in the {database} dataset"
        
        elif method == "Update":
            return f"{action} {obj} object with modified field values"
        
        elif method == "Select Tab":
            return f"{action} {obj} tab in the interface"
        
        elif "HV object" in method:
            position = "first" if "first" in method else "second"
            return f"{action} {obj} in the hierarchy viewer"
        
        else:
            return f"{action} {obj}"


class Method3_ContextAware:
    """方法3: 上下文感知规则（考虑工作流上下文）"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create",
            "Update": "Update",
            "Delete": "Delete",
            "Open Object": "Open",
            "Select Tab": "Navigate to",
            "Click Oneshot Button": "Click",
        }
        self.context_history = []
    
    def clean_object_name(self, obj: str) -> str:
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def extract_context(self, step: Dict) -> Dict:
        """提取上下文信息"""
        test_data = step.get('test_data', {})
        context = {}
        
        for section in ['create', 'update', 'editor']:
            if section in test_data and test_data[section]:
                data = test_data[section]
                for key, value in data.items():
                    if key.startswith('FLD_CSTM') and isinstance(value, dict):
                        context['spatial_context'] = value.get('Spatial Context')
                        context['station'] = value.get('Station Nummer')
                        context['attributes'] = [k for k in value.keys() 
                                                if k not in ['ID', 'Spatial Context', 'Station Nummer']]
        
        return context
    
    def infer_step_instruction(self, step: Dict) -> str:
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        database = step.get('database', '').replace(':', '')
        module = step.get('module', '')
        
        action = self.action_verbs.get(method, method)
        context = self.extract_context(step)
        
        # 构建详细指令
        instruction_parts = [action, obj]
        
        # 添加操作类型
        if method == "Create":
            if context.get('attributes'):
                key_attrs = context['attributes'][:2]  # 前两个属性
                if key_attrs:
                    instruction_parts.append(f"with properties: {', '.join(key_attrs)}")
        
        # 添加位置信息
        if context.get('spatial_context'):
            instruction_parts.append(f"in {context['spatial_context']} context")
        elif database:
            instruction_parts.append(f"in {database} dataset")
        
        # 添加模块信息（对于特殊操作）
        if module in ['Hierarchy Viewer', 'Datamodel Consistency Check']:
            instruction_parts.append(f"using {module}")
        
        instruction = " ".join(instruction_parts)
        
        # 保存到上下文
        self.context_history.append({
            'step': step.get('step_index'),
            'object': obj,
            'method': method
        })
        
        return instruction


# ============================================================
# 主评估程序
# ============================================================

def run_evaluation(test_size: int = 500):
    """运行完整评估"""
    
    print("="*70)
    print("指令生成方法评估系统")
    print("="*70)
    
    # 加载测试数据
    data_file = Path("data/processed/parsed_workflows.jsonl")
    
    if not data_file.exists():
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    # 收集测试步骤
    print(f"\n📥 加载测试数据 (取前{test_size}步)...")
    test_steps = []
    
    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                workflow = json.loads(line)
                test_steps.extend(workflow['steps'])
                if len(test_steps) >= test_size:
                    break
    
    test_steps = test_steps[:test_size]
    print(f"✅ 加载了 {len(test_steps)} 个测试步骤")
    
    # 初始化三种方法
    methods = {
        "方法1-基础规则": Method1_BasicRules(),
        "方法2-增强规则": Method2_EnhancedRules(),
        "方法3-上下文感知": Method3_ContextAware(),
    }
    
    # 初始化评估器
    evaluator = MethodEvaluator()
    
    # 评估每种方法
    summaries = {}
    for method_name, inferencer in methods.items():
        summary = evaluator.evaluate_method(inferencer, test_steps, method_name)
        summaries[method_name] = summary
        
        # 打印简要结果
        print(f"\n{method_name} 结果:")
        print(f"  综合评分: {summary['overall']['mean']:.3f}")
        print(f"  完整性: {summary['completeness']['mean']:.3f}")
        print(f"  可读性: {summary['readability']['mean']:.3f}")
        print(f"  速度: {summary['steps_per_second']:.1f} steps/sec")
    
    # 生成对比报告
    report = evaluator.compare_methods(summaries)
    print(report)
    
    # 保存详细结果
    output_dir = Path("data/processed/evaluation")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    evaluator.save_detailed_results(str(output_dir / "detailed_scores.json"))
    
    # 保存汇总报告
    with open(output_dir / "summary_report.json", 'w', encoding='utf-8') as f:
        json.dump(summaries, f, indent=2, ensure_ascii=False)
    
    with open(output_dir / "comparison_report.txt", 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 评估完成! 结果保存在: {output_dir}")
    
    return summaries, evaluator


if __name__ == "__main__":
    import sys
    
    # 可以通过命令行参数指定测试规模
    test_size = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    
    print(f"测试规模: {test_size} 步骤")
    summaries, evaluator = run_evaluation(test_size)
