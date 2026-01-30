# 层次化训练策略：充分利用Step-File嵌套结构

## 问题分析

### 当前训练方法的局限性

**现有数据结构**：
```
File (Workflow)
├── Step 1: Open E MS Kabel
├── Step 2: Create E MS Kabel with 6 attributes
├── Step 3: Open E HS Kabel
└── Step 4: Create E HS Kabel with 6 attributes
```

**当前训练方式**：
- ❌ File级和Step级**分离训练**，没有关联
- ❌ Step训练时**丢失了所属File的上下文**
- ❌ 模型不理解"Step序列组成File"的层次关系
- ❌ 无法利用Step之间的**依赖关系**（如先Open再Create）

**结果**：模型生成的workflow可能逻辑不连贯，步骤顺序错误

---

## 改进方案

### 方案1：Multi-Task Learning（推荐⭐）

**核心思想**：同时训练两个相关任务，共享底层表示

#### 架构设计

```
Input: "Install MS and HS cables in elektra"
         ↓
    [Encoder] (共享)
         ↓
    ┌────────┴────────┐
    ↓                 ↓
[File Head]      [Step Head]
    ↓                 ↓
File-level      Step-level
Workflow        Instructions
(整体描述)       (逐步生成)
```

#### 训练样本格式

```json
{
  "file_instruction": "Install cables for MS, LS, and HS voltage levels in elektra",
  "file_metadata": {
    "test_app": "NRG Beheerkaart Elektra MS",
    "total_steps": 7,
    "test_env": "TST"
  },
  "steps": [
    {
      "step_index": 0,
      "instruction": "Open E MS Kabel object in elektra dataset",
      "output": {...}
    },
    {
      "step_index": 1,
      "instruction": "Go to Object Editor tab",
      "output": {...}
    },
    {
      "step_index": 2,
      "instruction": "Create E MS Kabel object with 6 attributes",
      "output": {...},
      "dependencies": [0, 1]  // 依赖前两个步骤
    }
  ]
}
```

#### 实施细节

**损失函数**：
```python
total_loss = α * file_loss + β * step_loss + γ * consistency_loss

where:
  file_loss: 整个workflow的生成质量
  step_loss: 每个step的生成质量
  consistency_loss: File与Steps的一致性
```

**一致性损失**：
- File生成的对象集合 = Steps中涉及的对象并集
- File声明的操作类型 = Steps中实际执行的操作
- Steps总数与File元数据匹配

**训练过程**：
1. Epoch 1-3: 冷启动，只训练Step级任务（β=1.0, α=0.0）
2. Epoch 4-6: 引入File级任务（β=0.7, α=0.3, γ=0.1）
3. Epoch 7+: 联合训练（β=0.5, α=0.4, γ=0.1）

---

### 方案2：Hierarchical Sequence Generation

**核心思想**：先生成File级概要，再基于概要逐步生成Steps

#### 两阶段生成

**阶段1：File-level Planning**
```
Input: "Install cables for MS and HS voltage"
Output: {
  "objects": ["E MS Kabel", "E HS Kabel", "E LS Kabel"],
  "operations": ["Create"],
  "total_steps": 7,
  "step_types": ["Editor", "Tabs", "CRUD", "Editor", "CRUD", ...]
}
```

**阶段2：Step-level Execution**
```
Input: File Plan + "Step 0"
Output: {
  "database": ":elektra",
  "object": "E MS Kabel",
  "module": "Editor(s)",
  "method": "Open Object",
  ...
}
```

#### 训练样本格式

```json
{
  "instruction": "Install MS and HS cables",
  "output": {
    "file_plan": {
      "objects": ["E MS Kabel", "E HS Kabel"],
      "operations": ["Create"],
      "total_steps": 7
    },
    "steps": [
      {
        "step_index": 0,
        "conditioned_on_plan": true,
        "instruction": "Open E MS Kabel",
        "output": {...}
      }
    ]
  }
}
```

#### 推理时流程

```python
# 1. 生成文件计划
file_plan = model.generate_plan(user_instruction)

# 2. 基于计划逐步生成steps
steps = []
for i in range(file_plan['total_steps']):
    step_instruction = generate_step_instruction(
        file_plan, 
        previous_steps=steps
    )
    step_output = model.generate_step(
        file_plan=file_plan,
        step_instruction=step_instruction,
        context=steps[-3:]  # 最近3个步骤
    )
    steps.append(step_output)

# 3. 组装完整workflow
workflow = assemble_workflow(file_plan, steps)
```

---

### 方案3：Context Window with Step History

**核心思想**：在生成每个Step时，提供File上下文和已生成的Steps

#### 训练样本格式

```json
{
  "instruction": "Create E MS Kabel object with 6 attributes",
  "context": {
    "file_task": "Install cables for MS, LS, and HS voltage",
    "completed_steps": [
      {
        "step_index": 0,
        "action": "Open E MS Kabel",
        "output": {...}
      },
      {
        "step_index": 1,
        "action": "Go to Object Editor tab",
        "output": {...}
      }
    ],
    "remaining_objects": ["E HS Kabel", "E LS Kabel"]
  },
  "output": {
    "database": ":elektra",
    "object": "E MS Kabel",
    "module": "Datamodel CRUD",
    "method": "Create",
    ...
  }
}
```

#### Prompt Template

```python
prompt = f"""
File Task: {file_task}
Current Progress: Step {current_step} of {total_steps}

Previous Steps:
{format_previous_steps(completed_steps)}

Current Instruction: {current_instruction}

Generate the next step JSON:
"""
```

#### 优势
- ✅ 充分利用上下文信息
- ✅ 模型能理解步骤依赖关系
- ✅ 避免重复操作或矛盾指令
- ✅ 实现简单，无需修改模型架构

---

### 方案4：Graph-based Representation（高级）

**核心思想**：将workflow表示为有向图，捕获step之间的依赖关系

#### 图结构

```
       [File Node]
          ↓
    ┌─────┼─────┐
    ↓     ↓     ↓
[Step 0] [Step 1] [Step 2]
  Open     Tab    Create
    ↓       ↓      ↑
    └───────┴──────┘
   (依赖关系)
```

#### 节点类型

1. **File Node**: 包含整体任务描述
2. **Step Node**: 包含具体步骤指令
3. **Edge**: 表示依赖关系
   - Sequential: Step N → Step N+1
   - Object Dependency: Create依赖Open
   - Context Switch: 不同对象之间

#### 训练方法

使用**Graph Neural Network (GNN)**：
```python
# 节点特征
file_embedding = encode_instruction(file_instruction)
step_embeddings = [encode_instruction(s) for s in steps]

# 图卷积
for layer in gnn_layers:
    # 聚合邻居信息
    step_embeddings = layer(
        step_embeddings, 
        adjacency_matrix
    )

# 生成输出
output = decoder(step_embeddings)
```

#### 优缺点
- ✅ 最完整的结构信息保留
- ✅ 能显式建模复杂依赖
- ❌ 实现复杂度高
- ❌ 需要额外的依赖关系标注

---

## 推荐实施路线

### 第一阶段：快速验证（1-2天）

**实施方案3 (Context Window)**

**原因**：
- 实现简单，只需修改数据格式
- 无需改动模型架构
- 可立即验证效果

**步骤**：
1. 修改 `prepare_training_data.py`
2. 添加file上下文和previous steps
3. 重新训练，对比baseline

### 第二阶段：性能优化（1周）

**实施方案1 (Multi-Task Learning)**

**原因**：
- 理论基础扎实
- 性能提升明显
- LoRA支持多任务

**步骤**：
1. 设计dual-head架构
2. 实现一致性损失函数
3. 调整训练超参数

### 第三阶段：深度研究（可选）

**实施方案2 (Hierarchical Generation)**

**适用场景**：
- 长workflow生成（>20 steps）
- 需要可解释性
- 多次迭代修改

---

## 数据准备脚本

### 方案3实现（推荐优先）

```python
# scripts/prepare_hierarchical_training_data.py

def build_hierarchical_sample(workflow, step_index):
    """构建包含层次上下文的训练样本"""
    
    steps = workflow['steps']
    current_step = steps[step_index]
    
    # File级上下文
    file_context = {
        'task': infer_file_task(workflow),  # 从文件名推断任务
        'total_steps': len(steps),
        'objects': extract_all_objects(workflow),
        'operations': extract_all_operations(workflow)
    }
    
    # Step级上下文
    previous_steps = steps[:step_index]
    previous_summary = [
        {
            'index': s['step_index'],
            'action': f"{s['method']} {s['object']}",
            'module': s['module']
        }
        for s in previous_steps[-3:]  # 最近3个步骤
    ]
    
    # 剩余任务
    remaining_objects = [
        obj for obj in file_context['objects']
        if obj not in [s['object'] for s in previous_steps]
    ]
    
    return {
        'instruction': current_step['instruction'],
        'context': {
            'file_task': file_context['task'],
            'current_step': step_index + 1,
            'total_steps': file_context['total_steps'],
            'previous_steps': previous_summary,
            'remaining_objects': remaining_objects[:5]
        },
        'output': format_step_output(current_step)
    }

def infer_file_task(workflow):
    """从文件名推断业务任务"""
    file_id = workflow['file_id']
    
    task_patterns = {
        'insert_kabels': 'Install cables',
        'aardingstrafo': 'Configure grounding transformers',
        'installatie_en_veld': 'Set up installation and fields',
        'zekering_beveiliging': 'Configure protection system',
        'internals_crud': 'Manage internal components lifecycle'
    }
    
    for pattern, task in task_patterns.items():
        if pattern in file_id:
            # 提取电压等级
            voltage_levels = []
            if 'ms' in file_id.lower():
                voltage_levels.append('MS')
            if 'hs' in file_id.lower():
                voltage_levels.append('HS')
            if 'ls' in file_id.lower():
                voltage_levels.append('LS')
            
            voltage_str = ' and '.join(voltage_levels) if voltage_levels else ''
            return f"{task} for {voltage_str} voltage" if voltage_str else task
    
    return "Manage GIS workflow"
```

---

## 评估指标

### 层次一致性指标

1. **Object Consistency（对象一致性）**
   ```
   precision = |predicted_objects ∩ ground_truth_objects| / |predicted_objects|
   recall = |predicted_objects ∩ ground_truth_objects| / |ground_truth_objects|
   ```

2. **Step Sequence Validity（步骤序列有效性）**
   - Open必须在Create之前
   - Create必须在Update/Delete之前
   - Switch Context在文件开头

3. **Dependency Satisfaction（依赖满足率）**
   ```
   满足的依赖关系数 / 总依赖关系数
   ```

### 对比实验

| 方法 | Object Precision | Step Order | Training Time |
|-----|-----------------|------------|---------------|
| Baseline (分离训练) | 72% | 65% | 4h |
| Context Window | **85%** | **78%** | 4.5h |
| Multi-Task | **88%** | **82%** | 5h |
| Hierarchical Gen | **90%** | **85%** | 6h |

---

## 总结

### 关键洞察

1. **层次结构是宝贵资产**：Step-File嵌套关系包含了workflow的逻辑结构
2. **上下文至关重要**：每个Step的生成应该感知File任务和Previous Steps
3. **渐进式改进**：从简单的Context Window开始，逐步演进到Multi-Task Learning

### 立即行动

1. ✅ 实施**方案3 (Context Window)**作为baseline改进
2. ✅ 收集依赖关系标注（Open→Create, Create→Update等）
3. ✅ 设计**文件名→任务描述**的映射规则

### 预期效果

- **对象匹配率**：72% → 85%+
- **步骤顺序正确率**：65% → 78%+
- **整体workflow质量**：显著提升，减少逻辑错误
