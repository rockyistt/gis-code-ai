# 不使用API生成指令的替代方案

## 🎯 方案对比

如果无法使用Qwen/OpenAI API，你有以下替代方案：

| 方案 | 成本 | 质量 | 速度 | 难度 |
|-----|------|------|------|------|
| ✅ **规则模板**（推荐） | 免费 | 中 | 极快 | 简单 |
| OpenAI API | ¥10-50 | 高 | 快 | 简单 |
| 本地Ollama | 免费 | 中-高 | 中 | 中等 |
| Hugging Face模型 | 免费 | 中-高 | 慢 | 复杂 |
| 手动标注 | 免费 | 最高 | 极慢 | 简单 |

---

## ✅ 方案1：规则模板生成（强烈推荐）

### 优势
- ✅ **完全免费**，无需任何API
- ✅ **速度极快**，几秒处理4000+工作流
- ✅ **质量稳定**，根据评估报告，增强规则方法评分0.643
- ✅ **已经实现**，直接可用

### 使用方法

#### 快速开始
```powershell
# 使用增强规则方法（推荐）
python scripts/generate_instructions_rules.py --method enhanced

# 测试模式（只处理前10个）
python scripts/generate_instructions_rules.py --method enhanced --max-workflows 10
```

#### 三种规则方法

**1. basic（基础）- 简洁快速**
```python
# 示例输出
步骤级: "Create E MS Kabel"
文件级: "Test workflow to work with E MS Kabel, E HS Kabel in GIS system"
```

**2. enhanced（增强）- 推荐 ⭐**
```python
# 示例输出
步骤级: "Create a new E MS Kabel object with 5 attributes in elektra database"
文件级: "Workflow for NRG Beheerkaart Elektra MS: create E MS Kabel, E HS Kabel in elektra"
```
- 评分: 0.643（综合最高）
- 速度: 5,201 workflows/秒
- 特点: 包含数据库、属性数量等上下文

**3. context（上下文感知）- 最友好**
```python
# 示例输出
步骤级: "Create a new Medium Voltage Cable object"
文件级: "Electrical network workflow: object creation for Medium Voltage Cable and High Voltage Cable"
```
- 评分: 0.524
- 特点: 使用友好的术语，更易读

### 完整参数

```powershell
python scripts/generate_instructions_rules.py \
  --input data/processed/parsed_workflows.jsonl \
  --output-dir data/processed \
  --method enhanced \
  --max-workflows 100  # 可选：限制处理数量
```

### 输出文件

```
data/processed/
├── file_level_instructions_rule_enhanced.jsonl  # 文件级指令
└── step_level_instructions_rule_enhanced.jsonl  # 步骤级指令
```

---

## 🔄 方案2：OpenAI API（如果有预算）

如果你有OpenAI账号（比Qwen更常见）：

```powershell
# 设置API密钥
$env:OPENAI_API_KEY="sk-..."

# 运行
python src/data_processing/run_pipeline.py --provider openai
```

**成本估算**：
- GPT-4o-mini: ~¥10-20（4000个工作流）
- GPT-4: ~¥50-100

---

## 🖥️ 方案3：本地Ollama（无网络/隐私需求）

使用本地LLM，完全离线运行。

### 安装Ollama

```powershell
# 下载安装: https://ollama.com/download

# 安装模型（推荐）
ollama pull qwen2.5:7b        # 7GB，质量高
ollama pull qwen2.5:3b        # 3GB，速度快
ollama pull mistral:7b        # 7GB，英文优秀
```

### 修改代码支持Ollama

创建 `scripts/generate_instructions_ollama.py`:

```python
import ollama
import json
from pathlib import Path
from tqdm import tqdm

def generate_with_ollama(prompt: str, model: str = "qwen2.5:7b") -> str:
    response = ollama.generate(model=model, prompt=prompt)
    return response['response'].strip()

# 其余代码类似 generate_instructions_qwen.py
# 将 API 调用替换为 generate_with_ollama()
```

**优势**：
- ✅ 完全免费和离线
- ✅ 数据隐私
- ✅ 质量接近云端API

**劣势**：
- ❌ 需要GPU（CPU也可以但很慢）
- ❌ 需要下载大模型（3-7GB）
- ❌ 速度较慢（约10-30秒/workflow）

---

## 🤗 方案4：Hugging Face Transformers（最灵活）

使用开源模型，完全控制。

### 安装

```powershell
pip install transformers torch accelerate
```

### 代码示例

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# 加载模型（一次性，可缓存）
model_name = "Qwen/Qwen2.5-7B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto"
)

def generate_instruction(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "Generate GIS test instructions."},
        {"role": "user", "content": prompt}
    ]
    
    text = tokenizer.apply_chat_template(messages, tokenize=False)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    
    outputs = model.generate(**inputs, max_new_tokens=200)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)
```

**优势**：
- ✅ 完全免费
- ✅ 可自定义和微调
- ✅ 支持各种开源模型

**劣势**：
- ❌ 需要GPU（至少12GB显存）
- ❌ 设置复杂
- ❌ 首次下载模型需要时间

---

## ✋ 方案5：手动标注（高质量但费时）

如果只需要少量高质量数据（如template文件）：

### 流程

1. 读取 `parsed_workflows.jsonl`
2. 手动为每个workflow写描述
3. 保存为标准格式

### 工具脚本

```python
# scripts/manual_annotation.py
import json
from pathlib import Path

workflows = []
with open('data/processed/parsed_workflows.jsonl') as f:
    for line in f:
        workflows.append(json.loads(line))

# 只标注高质量模板
hq_workflows = [w for w in workflows if w.get('is_high_quality')]

print(f"需要标注 {len(hq_workflows)} 个高质量工作流")

for i, workflow in enumerate(hq_workflows):
    print(f"\n--- Workflow {i+1}/{len(hq_workflows)} ---")
    print(f"文件: {workflow['file_id']}")
    print(f"应用: {workflow.get('test_app')}")
    print(f"步骤数: {len(workflow.get('steps', []))}")
    
    # 显示步骤概览
    for j, step in enumerate(workflow['steps'][:3]):
        print(f"  步骤{j+1}: {step.get('method')} {step.get('object')}")
    
    # 输入标注
    instruction = input("\n请输入整体描述: ")
    workflow['manual_instruction'] = instruction

# 保存结果...
```

**优势**：
- ✅ 质量最高
- ✅ 完全可控

**劣势**：
- ❌ 极费时（4000个工作流需要几天）

---

## 🎯 推荐方案

### 立即可用：规则模板（方案1）

```powershell
# 1分钟搞定所有数据
python scripts/generate_instructions_rules.py --method enhanced
```

**适用场景**：
- ✅ 快速原型验证
- ✅ 无API预算
- ✅ 需要稳定输出
- ✅ 质量要求中等（评分0.643已经不错）

### 如果追求更高质量

1. **先用规则生成基础数据**（方案1）
2. **手动标注少量高质量样本**（方案5，只标注12个template）
3. **用高质量样本做few-shot**（提供给规则或本地模型参考）

### 如果有GPU

考虑使用 **Ollama**（方案3）：
- 一次安装，永久免费
- 质量接近API
- 适合长期项目

---

## 📊 质量对比（根据评估报告）

| 方法 | 综合评分 | 描述质量 | 业务逻辑 | 速度 |
|------|---------|---------|---------|------|
| **增强规则** | 0.643 | 0.513 | 0.479 | 5,201/s |
| 基础规则 | 0.556 | 0.371 | 0.136 | 2,794/s |
| 上下文感知 | 0.524 | 0.324 | 0.146 | 4,887/s |
| Qwen API | ~0.7-0.8 | ~0.6-0.7 | ~0.6-0.7 | ~1-2/s |

**结论**：增强规则方法的质量已经达到可用水平，特别适合快速迭代！

---

## 🚀 下一步行动

### 推荐流程

```powershell
# 第1步：使用规则生成所有数据（1分钟）
python scripts/generate_instructions_rules.py --method enhanced

# 第2步：查看生成效果
head -n 5 data/processed/file_level_instructions_rule_enhanced.jsonl

# 第3步：如果满意，直接用于训练
# 如果不满意，再考虑其他方案
```

### 混合策略（最佳实践）

```python
# 1. 规则生成所有数据（快速）
# 2. 手动标注12个高质量模板（1小时）
# 3. 用手动标注的做验证集
# 4. 用规则生成的做训练集
```

这样既保证了速度，又保证了质量！
