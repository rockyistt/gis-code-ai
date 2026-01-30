# Colab环境下加载和评估模型的完整脚本

# 在你的Colab notebook中按顺序运行这些单元格

# ============================================================
# 单元格1: 导入和基础设置
# ============================================================

import sys
import os
import json
import torch
import numpy as np
from pathlib import Path
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

print("✅ 基础库导入完成")

# ============================================================
# 单元格2: 定义模型加载函数
# ============================================================

class GISCodeGenerator:
    """GIS代码生成器 - CodeLlama + LoRA微调"""
    
    def __init__(
        self,
        model_path: str,
        base_model: str = "codellama/CodeLlama-7b-Instruct-hf",
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
        use_fp16: bool = True
    ):
        self.device = device
        self.use_fp16 = use_fp16
        
        print(f"🔧 初始化模型...")
        print(f"  设备: {device}")
        print(f"  FP16: {use_fp16}")
        
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"模型路径不存在: {model_path}")
        
        print(f"\n📖 加载Tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path),
            padding_side="right"
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        print(f"✅ Tokenizer加载完成")
        
        print(f"\n🤖 加载基础模型...")
        dtype = torch.float16 if use_fp16 else torch.float32
        
        base_model_obj = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=dtype,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        base_model_obj.config.use_cache = False
        print(f"✅ 基础模型加载完成")
        
        print(f"\n🔧 加载LoRA权重...")
        self.model = PeftModel.from_pretrained(
            base_model_obj,
            str(model_path),
            torch_dtype=dtype,
            device_map="auto",
        )
        self.model.eval()
        print(f"✅ LoRA权重加载完成")
        print(f"✅ 模型初始化完成！\n")
    
    def generate(
        self,
        instruction: str,
        context: str = "",
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Dict:
        """生成GIS代码"""
        
        if context:
            prompt = f"""You are a GIS workflow code generator. Generate complete JSON workflow code based on the instruction.

Instruction: {instruction}
Context: {context}

JSON Code:
"""
        else:
            prompt = f"""You are a GIS workflow code generator. Generate complete JSON workflow code based on the instruction.

Instruction: {instruction}

JSON Code:
"""
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=top_p,
                pad_token_id=self.tokenizer.pad_token_id,
            )
        
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        code = text.split("JSON Code:")[-1].strip()
        
        return {
            "instruction": instruction,
            "context": context,
            "generated_code": code
        }

print("✅ GISCodeGenerator类定义完成")

# ============================================================
# 单元格3: 加载模型
# ============================================================

# 指定Google Drive中的模型路径
MODEL_PATH = "/content/drive/MyDrive/gis-models/codellama-gis-lora"

print(f"📦 从Google Drive加载模型...")
print(f"   路径: {MODEL_PATH}\n")

generator = GISCodeGenerator(MODEL_PATH)

# ============================================================
# 单元格4: 快速测试推理
# ============================================================

print("=" * 70)
print("🧪 快速测试推理")
print("=" * 70)

test_cases = [
    {
        "instruction": "Create a new MS cable object at coordinates (186355533, 439556907)",
        "context": "Application: PowerGrid | Database: ND | Steps: 5"
    },
    {
        "instruction": "Open object in editor and verify field values",
        "context": "Application: NRG Elektra | Database: elektra | Steps: 3"
    },
    {
        "instruction": "Create and update cable object with hierarchy data",
        "context": "Application: GIS | Database: general | Steps: 4"
    }
]

for i, test in enumerate(test_cases, 1):
    print(f"\n📝 测试案例 {i}:")
    print(f"  指令: {test['instruction']}")
    print(f"  上下文: {test['context']}")
    
    result = generator.generate(test['instruction'], test['context'])
    
    print(f"\n  💻 生成代码 (前300字符):")
    code_preview = result['generated_code'][:300]
    print(f"  {code_preview}...")
    
    # 检查JSON有效性
    try:
        json.loads(result['generated_code'])
        print(f"  ✅ JSON有效")
    except:
        print(f"  ❌ JSON无效")

# ============================================================
# 单元格5: 定义评估指标
# ============================================================

def is_valid_json(text: str) -> bool:
    """检查是否为有效JSON"""
    try:
        json.loads(text)
        return True
    except:
        return False

def extract_json(text: str):
    """从文本中提取JSON"""
    try:
        return json.loads(text)
    except:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except:
                pass
        return None

def calculate_metrics(instruction, generated_output, reference_output):
    """计算评估指标"""
    
    metrics = {}
    
    # 1. JSON有效性
    metrics["json_valid"] = 1.0 if is_valid_json(generated_output) else 0.0
    
    # 2. 结构匹配度
    gen_json = extract_json(generated_output)
    ref_json = extract_json(reference_output)
    
    if gen_json and ref_json:
        # 检查必要字段
        gen_has_workflow = "workflow" in gen_json
        gen_steps = len(gen_json.get("workflow", {}).get("steps", [])) if gen_has_workflow else 0
        ref_steps = len(ref_json.get("workflow", {}).get("steps", [])) if "workflow" in ref_json else 0
        
        structure_score = 0.0
        if gen_has_workflow:
            if gen_steps > 0:
                # 检查每个step的必要字段
                required_fields = ["module", "method"]
                valid_steps = sum(
                    1 for step in gen_json["workflow"]["steps"]
                    if all(f in step for f in required_fields)
                )
                structure_score = valid_steps / gen_steps
            
            # 步骤数接近度
            if ref_steps > 0:
                length_ratio = min(gen_steps, ref_steps) / max(gen_steps, ref_steps)
                structure_score = 0.7 * structure_score + 0.3 * length_ratio
        
        metrics["structure_match"] = structure_score
        metrics["step_count"] = gen_steps
    else:
        metrics["structure_match"] = 0.0
        metrics["step_count"] = 0
    
    return metrics

print("✅ 评估指标函数定义完成")

# ============================================================
# 单元格6: 加载测试集并评估
# ============================================================

print("\n" + "=" * 70)
print("📂 加载测试数据")
print("=" * 70)

# 使用验证集作为测试集
TEST_DATA_PATH = "data/training/training_data_val.json"

with open(TEST_DATA_PATH, 'r', encoding='utf-8') as f:
    test_data = json.load(f)

print(f"✅ 加载了 {len(test_data)} 个测试样本")

# ============================================================
# 单元格7: 在测试集上评估模型 (取前50个样本快速测试)
# ============================================================

print("\n" + "=" * 70)
print("🧪 在测试集上评估模型")
print("=" * 70)

NUM_EVAL_SAMPLES = 50
print(f"评估样本数: {NUM_EVAL_SAMPLES}")

all_metrics = []
failed_count = 0

for i, sample in enumerate(tqdm(test_data[:NUM_EVAL_SAMPLES], desc="评估进度")):
    try:
        instruction = sample.get("instruction", "")
        context = sample.get("input", "")
        reference = sample.get("output", "")
        
        # 生成
        result = generator.generate(instruction, context)
        generated = result["generated_code"]
        
        # 计算指标
        metrics = calculate_metrics(instruction, generated, reference)
        all_metrics.append(metrics)
        
    except Exception as e:
        failed_count += 1
        all_metrics.append({"json_valid": 0.0, "structure_match": 0.0, "step_count": 0})

print(f"\n✅ 评估完成，失败样本: {failed_count}")

# ============================================================
# 单元格8: 打印评估结果
# ============================================================

print("\n" + "=" * 70)
print("📊 评估结果摘要")
print("=" * 70)

if all_metrics:
    json_valid_scores = [m["json_valid"] for m in all_metrics]
    structure_scores = [m["structure_match"] for m in all_metrics]
    step_counts = [m["step_count"] for m in all_metrics]
    
    print(f"\n✅ JSON有效性:")
    print(f"   平均: {np.mean(json_valid_scores):.2%}")
    print(f"   最小: {np.min(json_valid_scores):.2%}")
    print(f"   最大: {np.max(json_valid_scores):.2%}")
    
    print(f"\n🏗️  结构匹配度:")
    print(f"   平均: {np.mean(structure_scores):.2%}")
    print(f"   标准差: {np.std(structure_scores):.2%}")
    print(f"   最小: {np.min(structure_scores):.2%}")
    print(f"   最大: {np.max(structure_scores):.2%}")
    
    print(f"\n📍 步骤数统计:")
    print(f"   平均: {np.mean(step_counts):.1f}")
    print(f"   中位: {np.median(step_counts):.1f}")
    print(f"   最大: {np.max(step_counts):.0f}")
    
    # 综合评分
    overall_score = (
        0.3 * np.mean(json_valid_scores) +
        0.7 * np.mean(structure_scores)
    )
    
    print(f"\n🎯 综合评分: {overall_score:.2%}")
    
    if overall_score > 0.8:
        print(f"   等级: ⭐⭐⭐⭐⭐ 优秀")
    elif overall_score > 0.6:
        print(f"   等级: ⭐⭐⭐⭐ 良好")
    elif overall_score > 0.4:
        print(f"   等级: ⭐⭐⭐ 中等")
    else:
        print(f"   等级: ⭐⭐ 需要改进")

print("\n" + "=" * 70)

# ============================================================
# 单元格9: 保存详细结果 (可选)
# ============================================================

# 如果想保存详细结果到文件
OUTPUT_FILE = "/content/drive/MyDrive/gis-models/evaluation_results.json"

# 创建详细结果列表
detailed_results = []
for i, sample in enumerate(test_data[:NUM_EVAL_SAMPLES]):
    try:
        instruction = sample.get("instruction", "")
        context = sample.get("input", "")
        reference = sample.get("output", "")
        
        result = generator.generate(instruction, context)
        generated = result["generated_code"]
        
        metrics = calculate_metrics(instruction, generated, reference)
        
        detailed_results.append({
            "sample_id": i,
            "instruction": instruction,
            "metrics": metrics
        })
    except:
        pass

# 保存
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(detailed_results, f, indent=2, ensure_ascii=False)

print(f"💾 详细结果已保存到: {OUTPUT_FILE}")
