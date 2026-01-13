"""
文件级别（工作流级别）的评估系统

评估指标：
1. 工作流描述准确性
2. 步骤序列连贯性
3. 关键对象覆盖率
4. 操作流程完整性
5. 业务逻辑准确性
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics


# ============================================================
# 文件级别评估指标
# ============================================================

class WorkflowEvaluationMetrics:
    """工作流级别的评估指标"""
    
    @staticmethod
    def workflow_description_quality(file_instruction: str, workflow: Dict) -> float:
        """评估工作流描述质量"""
        score = 0.0
        
        # 1. 长度合理性 (20-150词)
        word_count = len(file_instruction.split())
        if 20 <= word_count <= 150:
            score += 0.25
        elif 10 <= word_count <= 200:
            score += 0.15
        
        # 2. 包含关键信息
        file_id = workflow.get('file_id', '')
        
        # 提取工作流中的所有对象
        objects = set()
        operations = set()
        for step in workflow.get('steps', []):
            obj = step.get('object', '')
            if obj:
                objects.add(obj)
            method = step.get('method', '')
            if method:
                operations.add(method)
        
        # 检查是否提及主要对象
        mentioned_objects = sum(1 for obj in objects if obj in file_instruction)
        if objects:
            object_coverage = mentioned_objects / len(objects)
            score += object_coverage * 0.30
        
        # 检查是否提及主要操作
        mentioned_ops = sum(1 for op in operations if op.lower() in file_instruction.lower())
        if operations:
            op_coverage = mentioned_ops / len(operations)
            score += op_coverage * 0.25
        
        # 3. 是否说明了业务目的
        purpose_keywords = ['test', 'create', 'configure', 'setup', 'workflow', 
                           'manage', 'verify', 'check', 'process']
        if any(kw in file_instruction.lower() for kw in purpose_keywords):
            score += 0.20
        
        return min(score, 1.0)
    
    @staticmethod
    def step_coherence_score(step_instructions: List[str]) -> float:
        """评估步骤指令的连贯性"""
        if len(step_instructions) < 2:
            return 1.0
        
        score = 0.0
        
        # 1. 检查是否有重复步骤描述
        unique_ratio = len(set(step_instructions)) / len(step_instructions)
        if unique_ratio > 0.9:
            score += 0.3
        elif unique_ratio > 0.7:
            score += 0.2
        
        # 2. 检查步骤是否有逻辑顺序词
        sequence_words = ['first', 'then', 'next', 'after', 'finally', 'before']
        has_sequence = sum(1 for inst in step_instructions 
                          if any(sw in inst.lower() for sw in sequence_words))
        if has_sequence > 0:
            score += 0.2
        
        # 3. 检查相邻步骤是否相关
        coherent_pairs = 0
        for i in range(len(step_instructions) - 1):
            inst1 = set(step_instructions[i].lower().split())
            inst2 = set(step_instructions[i + 1].lower().split())
            overlap = len(inst1 & inst2)
            if overlap > 0:  # 有共同词汇
                coherent_pairs += 1
        
        if len(step_instructions) > 1:
            coherence_ratio = coherent_pairs / (len(step_instructions) - 1)
            score += coherence_ratio * 0.3
        
        # 4. 步骤长度一致性
        lengths = [len(inst.split()) for inst in step_instructions]
        if len(lengths) > 1:
            avg_len = statistics.mean(lengths)
            variance = statistics.variance(lengths)
            if variance < avg_len:  # 方差小于均值说明比较一致
                score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def key_object_coverage(file_instruction: str, step_instructions: List[str], 
                           workflow: Dict) -> float:
        """评估关键对象的覆盖率"""
        # 提取工作流中的所有对象
        objects = []
        for step in workflow.get('steps', []):
            obj = step.get('object', '')
            if obj and obj not in ['Object Editor', 'Hierarchy Viewer']:
                objects.append(obj)
        
        if not objects:
            return 1.0
        
        # 统计唯一对象
        unique_objects = set(objects)
        
        # 检查文件级指令的覆盖
        file_coverage = sum(1 for obj in unique_objects 
                          if obj in file_instruction)
        
        # 检查步骤级指令的覆盖
        all_step_text = ' '.join(step_instructions)
        step_coverage = sum(1 for obj in unique_objects 
                          if obj in all_step_text)
        
        # 综合评分
        file_score = file_coverage / len(unique_objects) if unique_objects else 1.0
        step_score = step_coverage / len(unique_objects) if unique_objects else 1.0
        
        return (file_score * 0.4 + step_score * 0.6)
    
    @staticmethod
    def operation_flow_completeness(step_instructions: List[str], workflow: Dict) -> float:
        """评估操作流程的完整性"""
        steps = workflow.get('steps', [])
        
        if not steps:
            return 1.0
        
        score = 0.0
        
        # 1. 所有步骤都有指令
        if len(step_instructions) == len(steps):
            score += 0.3
        else:
            score += (len(step_instructions) / len(steps)) * 0.3
        
        # 2. 关键操作类型都被覆盖
        operation_types = set(step.get('method', '') for step in steps)
        mentioned_operations = set()
        
        for inst in step_instructions:
            inst_lower = inst.lower()
            for op in operation_types:
                if op.lower() in inst_lower:
                    mentioned_operations.add(op)
        
        if operation_types:
            op_coverage = len(mentioned_operations) / len(operation_types)
            score += op_coverage * 0.3
        
        # 3. CRUD操作的完整性
        crud_ops = {'Create': False, 'Update': False, 'Delete': False}
        workflow_has_crud = set()
        
        for step in steps:
            method = step.get('method', '')
            if method in crud_ops:
                workflow_has_crud.add(method)
        
        if workflow_has_crud:
            crud_mentioned = set()
            for inst in step_instructions:
                inst_lower = inst.lower()
                for op in workflow_has_crud:
                    if op.lower() in inst_lower:
                        crud_mentioned.add(op)
            
            crud_score = len(crud_mentioned) / len(workflow_has_crud)
            score += crud_score * 0.2
        else:
            score += 0.2  # 没有CRUD操作也给分
        
        # 4. 步骤顺序的保持
        # 检查是否保持了原始的对象顺序
        workflow_objects = [step.get('object', '') for step in steps if step.get('object')]
        instruction_objects = []
        for inst in step_instructions:
            for obj in workflow_objects:
                if obj in inst and obj not in instruction_objects:
                    instruction_objects.append(obj)
        
        # 计算顺序保持率
        if len(workflow_objects) > 1 and len(instruction_objects) > 1:
            order_preserved = sum(1 for i in range(len(instruction_objects) - 1)
                                if workflow_objects.index(instruction_objects[i]) < 
                                   workflow_objects.index(instruction_objects[i + 1]))
            order_score = order_preserved / (len(instruction_objects) - 1)
            score += order_score * 0.2
        else:
            score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def business_logic_accuracy(file_instruction: str, workflow: Dict) -> float:
        """评估业务逻辑的准确性"""
        score = 0.0
        
        # 1. 识别工作流类型
        file_id = workflow.get('file_id', '').lower()
        is_template = workflow.get('is_high_quality', False)
        
        # 如果是模板，应该提及
        if is_template:
            if 'template' in file_instruction.lower():
                score += 0.2
        
        # 2. 识别测试类型
        test_cases = workflow.get('test_cases', [])
        if test_cases and test_cases[0]:
            test_type = test_cases[0][0] if test_cases[0] else ''
            
            # 检查是否正确识别测试类型
            type_keywords = {
                'CRUD': ['create', 'update', 'delete', 'crud', 'data'],
                'Editor': ['editor', 'open', 'edit'],
                'Navigation': ['navigate', 'select', 'tab', 'button']
            }
            
            for key, keywords in type_keywords.items():
                if key.lower() in test_type.lower():
                    if any(kw in file_instruction.lower() for kw in keywords):
                        score += 0.2
                        break
        
        # 3. 识别主要数据库/应用
        test_app = workflow.get('test_app', '')
        if test_app:
            # 提取应用的关键词
            app_words = test_app.lower().split()
            mentioned = sum(1 for word in app_words 
                          if len(word) > 3 and word in file_instruction.lower())
            if mentioned > 0:
                score += 0.2
        
        # 4. 识别主要操作模式
        steps = workflow.get('steps', [])
        create_count = sum(1 for s in steps if s.get('method') == 'Create')
        update_count = sum(1 for s in steps if s.get('method') == 'Update')
        delete_count = sum(1 for s in steps if s.get('method') == 'Delete')
        
        # 如果有创建操作，应该提及
        if create_count > 0 and 'create' in file_instruction.lower():
            score += 0.15
        
        # 如果有更新操作，应该提及
        if update_count > 0 and 'update' in file_instruction.lower():
            score += 0.15
        
        # 如果是完整的CRUD，应该有完整性的描述
        if create_count > 0 and update_count > 0 and delete_count > 0:
            if any(word in file_instruction.lower() 
                   for word in ['full', 'complete', 'entire', 'comprehensive']):
                score += 0.1
        
        return min(score, 1.0)


# ============================================================
# 文件级别评估器
# ============================================================

class WorkflowEvaluator:
    """工作流级别的评估器"""
    
    def __init__(self):
        self.metrics = WorkflowEvaluationMetrics()
        self.results = []
    
    def evaluate_workflow(self, file_instruction: str, step_instructions: List[str],
                         workflow: Dict, method_name: str) -> Dict[str, float]:
        """评估单个工作流"""
        scores = {
            "description_quality": self.metrics.workflow_description_quality(
                file_instruction, workflow
            ),
            "step_coherence": self.metrics.step_coherence_score(step_instructions),
            "object_coverage": self.metrics.key_object_coverage(
                file_instruction, step_instructions, workflow
            ),
            "flow_completeness": self.metrics.operation_flow_completeness(
                step_instructions, workflow
            ),
            "business_logic": self.metrics.business_logic_accuracy(
                file_instruction, workflow
            )
        }
        
        # 计算综合评分
        scores["overall"] = (
            scores["description_quality"] * 0.25 +
            scores["step_coherence"] * 0.20 +
            scores["object_coverage"] * 0.20 +
            scores["flow_completeness"] * 0.20 +
            scores["business_logic"] * 0.15
        )
        
        return scores
    
    def evaluate_method(self, inferencer, workflows: List[Dict], 
                       method_name: str) -> Dict[str, Any]:
        """评估一个方法在所有工作流上的表现"""
        print(f"\n评估方法: {method_name}")
        print("-" * 60)
        
        all_scores = []
        start_time = time.time()
        
        for i, workflow in enumerate(workflows):
            if (i + 1) % 10 == 0:
                print(f"  进度: {i + 1}/{len(workflows)}")
            
            try:
                # 生成文件级指令
                file_instruction = inferencer.infer_workflow_instruction(workflow)
                
                # 生成步骤级指令
                step_instructions = []
                for step in workflow['steps']:
                    step_inst = inferencer.infer_step_instruction(step)
                    step_instructions.append(step_inst)
                
                # 评估
                scores = self.evaluate_workflow(
                    file_instruction, step_instructions, workflow, method_name
                )
                scores['file_id'] = workflow['file_id']
                scores['is_high_quality'] = workflow.get('is_high_quality', False)
                all_scores.append(scores)
                
            except Exception as e:
                print(f"  ⚠️  工作流 {workflow.get('file_id')} 失败: {e}")
                continue
        
        elapsed_time = time.time() - start_time
        
        # 计算统计信息
        summary = self.calculate_summary(all_scores, elapsed_time, len(workflows))
        summary['method_name'] = method_name
        
        return summary, all_scores
    
    def calculate_summary(self, all_scores: List[Dict[str, float]], 
                         elapsed_time: float, total_workflows: int) -> Dict[str, Any]:
        """计算汇总统计"""
        if not all_scores:
            return {"error": "No valid scores"}
        
        summary = {
            "total_workflows": total_workflows,
            "successful_workflows": len(all_scores),
            "elapsed_time": elapsed_time,
            "workflows_per_second": len(all_scores) / elapsed_time if elapsed_time > 0 else 0,
        }
        
        # 计算每个指标的统计
        metrics = ["overall", "description_quality", "step_coherence", 
                  "object_coverage", "flow_completeness", "business_logic"]
        
        for metric in metrics:
            values = [s[metric] for s in all_scores]
            summary[metric] = {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values),
                "max": max(values)
            }
        
        # 按质量分组统计
        high_quality = [s for s in all_scores if s.get('is_high_quality', False)]
        regular = [s for s in all_scores if not s.get('is_high_quality', False)]
        
        if high_quality:
            summary['high_quality_mean'] = statistics.mean(
                [s['overall'] for s in high_quality]
            )
        
        if regular:
            summary['regular_mean'] = statistics.mean(
                [s['overall'] for s in regular]
            )
        
        return summary
    
    def generate_report(self, summaries: Dict[str, Dict], 
                       detailed_scores: Dict[str, List]) -> str:
        """生成对比报告"""
        report = [
            "\n" + "="*70,
            "文件级别评估对比报告",
            "="*70,
        ]
        
        # 核心指标对比
        report.append("\n📊 核心指标对比 (工作流级别):")
        report.append("-" * 70)
        
        metrics_display = {
            "综合评分": "overall",
            "描述质量": "description_quality",
            "步骤连贯性": "step_coherence",
            "对象覆盖": "object_coverage",
            "流程完整性": "flow_completeness",
            "业务逻辑": "business_logic"
        }
        
        header = f"{'指标':<15} " + " ".join(f"{name:>18}" for name in summaries.keys())
        report.append(header)
        report.append("-" * 70)
        
        for display_name, metric in metrics_display.items():
            row = f"{display_name:<15} "
            for method_name in summaries.keys():
                if metric in summaries[method_name]:
                    value = summaries[method_name][metric]['mean']
                    row += f"{value:>18.3f} "
                else:
                    row += f"{'N/A':>18} "
            report.append(row)
        
        # 性能对比
        report.append("\n⚡ 性能对比:")
        report.append("-" * 70)
        for method_name, summary in summaries.items():
            wps = summary.get('workflows_per_second', 0)
            time_val = summary.get('elapsed_time', 0)
            report.append(f"{method_name:<20} {wps:>10.1f} workflows/sec  ({time_val:.2f}s total)")
        
        # 按质量分组对比
        report.append("\n📈 按数据质量分组:")
        report.append("-" * 70)
        
        for method_name, summary in summaries.items():
            report.append(f"\n{method_name}:")
            if 'high_quality_mean' in summary:
                report.append(f"  高质量模板: {summary['high_quality_mean']:.3f}")
            if 'regular_mean' in summary:
                report.append(f"  普通工作流: {summary['regular_mean']:.3f}")
        
        # 推荐
        report.append("\n\n🏆 推荐:")
        report.append("-" * 70)
        
        best_overall = max(summaries.items(), 
                          key=lambda x: x[1].get('overall', {}).get('mean', 0))
        fastest = max(summaries.items(),
                     key=lambda x: x[1].get('workflows_per_second', 0))
        
        report.append(f"最佳质量: {best_overall[0]} "
                     f"(综合评分: {best_overall[1]['overall']['mean']:.3f})")
        report.append(f"最快速度: {fastest[0]} "
                     f"({fastest[1]['workflows_per_second']:.1f} workflows/sec)")
        
        return "\n".join(report)


# ============================================================
# 三种方法的实现（真正不同的实现）
# ============================================================

import sys
from pathlib import Path
# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入SimpleInferencer
import importlib.util
spec = importlib.util.spec_from_file_location(
    "demo_inference", 
    project_root / "examples" / "demo_inference.py"
)
demo_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo_module)
SimpleInferencer = demo_module.SimpleInferencer


class Method1_BasicRules:
    """方法1: 基础规则 - 简洁快速"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create",
            "Update": "Update",
            "Delete": "Delete",
            "Open Object": "Open",
            "Select Tab": "Navigate to",
            "Click Oneshot Button": "Click",
        }
    
    def clean_object_name(self, obj: str) -> str:
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def infer_step_instruction(self, step: Dict) -> str:
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        action = self.action_verbs.get(method, method)
        return f"{action} {obj}"
    
    def infer_workflow_instruction(self, workflow: Dict) -> str:
        """简洁的工作流描述"""
        steps = workflow.get('steps', [])
        
        # 提取主要操作
        create_objects = []
        for step in steps:
            if step.get('method') == 'Create':
                obj = self.clean_object_name(step.get('object', ''))
                if obj not in create_objects:
                    create_objects.append(obj)
        
        if create_objects:
            if len(create_objects) == 1:
                return f"Test workflow to create {create_objects[0]} in the GIS system"
            else:
                return f"Test workflow to create multiple objects ({', '.join(create_objects[:3])}) in the GIS system"
        else:
            return f"Test workflow for {workflow.get('file_id', 'GIS operations')}"


class Method2_EnhancedRules:
    """方法2: 增强规则 - 详细完整"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create a new",
            "Update": "Update the existing",
            "Delete": "Delete the",
            "Open Object": "Open",
            "Select Tab": "Navigate to the",
            "Click Oneshot Button": "Click the",
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
        
        if method == "Create":
            attr_count = self.extract_attributes_count(step)
            if attr_count > 0:
                return f"{action} {obj} object with {attr_count} specified attributes in {database}"
            return f"{action} {obj} object in {database}"
        elif method in ["Open Object", "Open Object with ID"]:
            return f"{action} {obj} object in the {database} dataset"
        else:
            return f"{action} {obj}"
    
    def infer_workflow_instruction(self, workflow: Dict) -> str:
        """详细的工作流描述，包含更多上下文信息"""
        file_id = workflow.get('file_id', '')
        is_template = workflow.get('is_high_quality', False)
        test_app = workflow.get('test_app', '')
        steps = workflow.get('steps', [])
        
        # 分析操作类型
        create_objects = []
        update_objects = []
        delete_objects = []
        databases = set()
        
        for step in steps:
            method = step.get('method', '')
            obj = self.clean_object_name(step.get('object', ''))
            db = step.get('database', '').replace(':', '')
            
            if db:
                databases.add(db)
            
            if method == 'Create' and obj not in create_objects:
                create_objects.append(obj)
            elif method == 'Update' and obj not in update_objects:
                update_objects.append(obj)
            elif method == 'Delete' and obj not in delete_objects:
                delete_objects.append(obj)
        
        # 构建描述
        prefix = "Template workflow" if is_template else "Test workflow"
        
        # 添加应用信息
        if test_app:
            prefix += f" for {test_app}"
        
        # 添加操作描述
        operations = []
        if create_objects:
            obj_list = ', '.join(create_objects[:3])
            if len(create_objects) > 3:
                obj_list += f" and {len(create_objects) - 3} more"
            operations.append(f"create {obj_list}")
        
        if update_objects:
            operations.append(f"update {len(update_objects)} objects")
        
        if delete_objects:
            operations.append(f"delete {len(delete_objects)} objects")
        
        # 添加数据库信息
        db_info = ""
        if databases:
            db_list = ', '.join(list(databases)[:2])
            db_info = f" in {db_list} dataset"
        
        if operations:
            return f"{prefix}: {', '.join(operations)}{db_info}"
        else:
            return f"{prefix}: perform operations on GIS objects{db_info}"


class Method3_ContextAware:
    """方法3: 上下文感知 - 考虑业务逻辑"""
    
    def __init__(self):
        self.action_verbs = {
            "Create": "Create",
            "Update": "Update",
            "Delete": "Delete",
            "Open Object": "Open",
            "Select Tab": "Navigate to",
        }
        
        # 术语映射
        self.term_mapping = {
            "E MS Kabel": "Medium Voltage Cable",
            "E HS Kabel": "High Voltage Cable", 
            "E LS Kabel": "Low Voltage Cable",
            "E Stationcomplex": "Station Complex",
            "E MS Installatie": "MS Installation",
            "E HS Aardingstrafo": "HS Grounding Transformer",
            "E MS Aardingstrafo": "MS Grounding Transformer",
        }
    
    def clean_object_name(self, obj: str) -> str:
        if obj.startswith(':'):
            obj = obj[1:]
        return obj
    
    def translate_object(self, obj: str) -> str:
        """翻译技术名称为友好名称"""
        return self.term_mapping.get(obj, obj)
    
    def infer_step_instruction(self, step: Dict) -> str:
        method = step.get('method', '')
        obj = self.clean_object_name(step.get('object', ''))
        friendly_obj = self.translate_object(obj)
        action = self.action_verbs.get(method, method)
        
        return f"{action} {friendly_obj}"
    
    def identify_workflow_type(self, workflow: Dict) -> str:
        """识别工作流类型"""
        test_cases = workflow.get('test_cases', [])
        if test_cases and test_cases[0]:
            test_type = test_cases[0][0] if test_cases[0] else ''
            
            if 'CRUD' in test_type:
                return "CRUD operations"
            elif 'Editor' in test_type:
                return "editor operations"
            elif 'Navigation' in test_type:
                return "navigation"
        
        # 从步骤推断
        steps = workflow.get('steps', [])
        has_create = any(s.get('method') == 'Create' for s in steps)
        has_update = any(s.get('method') == 'Update' for s in steps)
        has_delete = any(s.get('method') == 'Delete' for s in steps)
        
        if has_create and has_update and has_delete:
            return "full CRUD operations"
        elif has_create:
            return "object creation"
        elif has_update:
            return "object modification"
        
        return "GIS operations"
    
    def infer_workflow_instruction(self, workflow: Dict) -> str:
        """上下文感知的工作流描述，强调业务逻辑"""
        file_id = workflow.get('file_id', '')
        is_template = workflow.get('is_high_quality', False)
        test_app = workflow.get('test_app', '')
        steps = workflow.get('steps', [])
        
        # 识别工作流类型
        workflow_type = self.identify_workflow_type(workflow)
        
        # 提取关键对象并翻译
        key_objects = set()
        for step in steps:
            method = step.get('method', '')
            if method in ['Create', 'Update']:
                obj = self.clean_object_name(step.get('object', ''))
                friendly_obj = self.translate_object(obj)
                key_objects.add(friendly_obj)
        
        # 构建描述
        prefix = "Template" if is_template else "Test workflow"
        
        # 添加应用信息
        app_info = ""
        if test_app:
            # 提取应用关键词
            if "Elektra" in test_app:
                app_info = " for electrical network"
            elif "Gas" in test_app:
                app_info = " for gas network"
            else:
                app_info = f" for {test_app}"
        
        # 添加对象信息
        obj_info = ""
        if key_objects:
            obj_list = list(key_objects)[:3]
            if len(obj_list) == 1:
                obj_info = f" involving {obj_list[0]}"
            elif len(obj_list) == 2:
                obj_info = f" involving {obj_list[0]} and {obj_list[1]}"
            else:
                obj_info = f" involving {', '.join(obj_list[:2])}, and more"
        
        return f"{prefix}{app_info}: {workflow_type}{obj_info}"


# ============================================================
# 主评估程序
# ============================================================

def run_workflow_evaluation(test_size: int = 100):
    """运行工作流级别的评估"""
    
    print("="*70)
    print("工作流级别评估系统")
    print("="*70)
    
    # 加载测试数据
    data_file = Path("data/processed/parsed_workflows.jsonl")
    
    if not data_file.exists():
        print(f"❌ 数据文件不存在: {data_file}")
        return
    
    print(f"\n📥 加载测试数据 (取前{test_size}个工作流)...")
    workflows = []
    
    with open(data_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= test_size:
                break
            if line.strip():
                workflows.append(json.loads(line))
    
    print(f"✅ 加载了 {len(workflows)} 个工作流")
    print(f"   - 高质量模板: {sum(1 for w in workflows if w.get('is_high_quality'))}")
    print(f"   - 普通工作流: {sum(1 for w in workflows if not w.get('is_high_quality'))}")
    
    # 初始化三种方法
    methods = {
        "方法1-基础规则": Method1_BasicRules(),
        "方法2-增强规则": Method2_EnhancedRules(),
        "方法3-上下文感知": Method3_ContextAware(),
    }
    
    # 初始化评估器
    evaluator = WorkflowEvaluator()
    
    # 评估每种方法
    all_summaries = {}
    all_detailed_scores = {}
    
    for method_name, inferencer in methods.items():
        summary, detailed = evaluator.evaluate_method(inferencer, workflows, method_name)
        all_summaries[method_name] = summary
        all_detailed_scores[method_name] = detailed
        
        # 打印简要结果
        print(f"\n{method_name} 结果:")
        print(f"  综合评分: {summary['overall']['mean']:.3f}")
        print(f"  描述质量: {summary['description_quality']['mean']:.3f}")
        print(f"  步骤连贯: {summary['step_coherence']['mean']:.3f}")
        print(f"  对象覆盖: {summary['object_coverage']['mean']:.3f}")
        print(f"  流程完整: {summary['flow_completeness']['mean']:.3f}")
        print(f"  业务逻辑: {summary['business_logic']['mean']:.3f}")
    
    # 生成对比报告
    report = evaluator.generate_report(all_summaries, all_detailed_scores)
    print(report)
    
    # 保存结果
    output_dir = Path("data/processed/evaluation")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # 保存汇总
    with open(output_dir / "workflow_summary.json", 'w', encoding='utf-8') as f:
        json.dump(all_summaries, f, indent=2, ensure_ascii=False)
    
    # 保存详细评分
    with open(output_dir / "workflow_detailed_scores.json", 'w', encoding='utf-8') as f:
        json.dump(all_detailed_scores, f, indent=2, ensure_ascii=False)
    
    # 保存报告
    with open(output_dir / "workflow_report.txt", 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 评估完成! 结果保存在: {output_dir}")
    print(f"   - workflow_summary.json: 汇总统计")
    print(f"   - workflow_detailed_scores.json: 详细评分")
    print(f"   - workflow_report.txt: 文本报告")
    
    return all_summaries, all_detailed_scores


if __name__ == "__main__":
    import sys
    
    # 可以通过命令行参数指定测试规模
    test_size = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    
    print(f"测试规模: {test_size} 个工作流")
    summaries, detailed = run_workflow_evaluation(test_size)
