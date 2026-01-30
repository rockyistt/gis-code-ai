# ⚡ Colab显存优化 - 快速参考卡

## 🆘 如果你看到这个错误：
```
RuntimeError: CUDA out of memory
```

---

## 最快的修复方案（按顺序尝试）

### 1️⃣ 重启kernel（90%的情况能解决）
```
Ctrl + M → 选择"Restart runtime"
等待60秒
重新运行代码
```

### 2️⃣ 减少样本数
```python
# 在评估cell中找到这一行：
NUM_EVAL_SAMPLES = 50  # 改为 20 或 10

# 再运行该cell
```

### 3️⃣ 启用8-bit量化
```python
# 已经在代码中了！确保运行的是最新的notebook
# 代码中有try-except自动处理

# 如果失败，手动改成：
load_in_8bit=True
```

### 4️⃣ 减少生成长度
```python
# 在generate_code函数中改：
max_new_tokens=128  # 从256改为128
```

### 5️⃣ CPU推理（最后手段，会很慢）
```python
model = model.to("cpu")
device = "cpu"
```

---

## 内存占用速查表

```
CodeLlama-7B on T4 GPU (12GB):

float32:     ❌ 14GB（超出）
float16:     ⚠️ 7GB（勉强）
8-bit:       ✅ 4GB（推荐）
4-bit:       ✅ 2GB（最激进）

选择: 8-bit!
```

---

## 推荐操作流程

### ✅ 必须做的：
1. **加载前**：重启kernel
2. **加载时**：使用8-bit（已内置）
3. **评估时**：减少样本数到50以内
4. **完成后**：关闭notebook

### ❌ 不要做的：
- ❌ 不要在同一kernel运行多个任务
- ❌ 不要保持长时间的大tensor
- ❌ 不要尝试float32加载
- ❌ 不要同时运行多个notebook

---

## 应急清理命令

如果仍在OOM边缘：

```python
import gc
import torch

# 立即清理
gc.collect()
torch.cuda.empty_cache()

# 检查现在的内存
torch.cuda.memory_allocated() / 1024**3  # 单位：GB
```

---

## 快速诊断

运行这个检查可用内存：

```python
import torch
import psutil

mem = psutil.virtual_memory()
print(f"系统: {mem.available/1024**3:.1f}GB 可用")
print(f"GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB 已用")
print(f"GPU: {torch.cuda.get_device_properties(0).total_memory/1024**3:.1f}GB 总量")

# 如果可用<12GB → 有问题 → 重启kernel
```

---

## 核心数字要记住

- T4 GPU: 12GB（很紧）
- A100 GPU: 40GB（舒适）
- CodeLlama-7B float16: 7GB
- CodeLlama-7B 8-bit: 4GB
- 推荐max_tokens: 256
- 推荐样本数: 50
- 推荐batch_size: 1

---

## 一句话总结

🔑 **使用8-bit量化（已内置），减少样本数到50个，重启kernel。**

---

Created: 2026-01-28
