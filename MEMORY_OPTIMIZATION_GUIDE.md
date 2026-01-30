# 🚀 Colab内存优化指南

## 问题诊断

当你看到错误信息时：
```
RuntimeError: CUDA out of memory. Tried to allocate XXX.XX GiB
```

或者kernel直接crash（没有错误信息，session自动重启），说明显存已用尽。

---

## 🔥 已实现的优化（Train_GIS_Model_Colab.ipynb）

### 1. **8-bit量化加载** ⭐⭐⭐ (最重要)
```python
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    load_in_8bit=True,  # 关键！
    device_map="auto",
)
```
- **效果**：减少40%内存占用（14GB → 8GB）
- **精度损失**：<1%，基本无感知
- **前置条件**：需要安装`bitsandbytes`

**对比：**
| 加载方式 | 内存占用 | 精度 | 速度 |
|---------|--------|------|------|
| float32 | 14GB+ | 100% | 正常 |
| float16 | 7GB+ | 99.9% | 正常 |
| **8-bit** | **4-5GB** | **99%** | **正常** |
| 4-bit | 2-3GB | 98% | 正常 |

### 2. **device_map="auto"** ⭐⭐
```python
device_map="auto"  # 自动分布模型层
```
- **效果**：模型层自动分布在GPU和CPU间
- **原理**：满载GPU优先，剩余层放CPU内存
- **缺点**：GPU-CPU间数据移动有性能开销（10-20%）

### 3. **减少max_new_tokens**
```python
outputs = model.generate(
    ...,
    max_new_tokens=256,  # 原来512，现在256
)
```
- **效果**：减少KV缓存占用
- **关系**：KV缓存 = batch_size × seq_len × hidden_dim
- **权衡**：生成长度变短，但通常足够

### 4. **清理内存垃圾**
```python
import gc
gc.collect()
torch.cuda.empty_cache()  # 释放显存碎片
```
- **何时运行**：
  - 加载前：清理前面的变量
  - 推理后：释放输入tensor
  - 评估结束：卸载模型

### 5. **内存预检查**
```python
# 评估前检查可用内存
if available_memory < 12GB:
    print("⚠️ 内存不足")
```
- **好处**：提前发现问题，避免OOM中途crash

---

## 📊 内存占用快速参考

假设使用CodeLlama-7B在T4 GPU（12GB）上：

| 组件 | 占用 | 备注 |
|------|------|------|
| **float16基础模型** | 7GB | 7B × 2字节 |
| **float32基础模型** | 14GB | 7B × 4字节（超出T4） |
| **8-bit量化** | 4GB | 7B × 1字节 |
| **LoRA权重** | 0.2GB | 通常很小 |
| **Tokenizer** | <0.1GB | 词汇表 |
| **推理KV缓存** | 1-2GB | 随序列长度增长 |
| **系统保留** | ~2GB | OS和其他应用 |

**总计**：float16版本约11GB（T4勉强），8-bit版本约6GB（舒适）

---

## ✅ 使用清单

### 加载模型前：
- [ ] 重启kernel（确保内存干净）
- [ ] 运行"内存预检查"cell
- [ ] 确认可用内存>12GB
- [ ] 已安装bitsandbytes（用于8-bit）

### 加载模型时：
- [ ] 使用`load_in_8bit=True`
- [ ] 使用`device_map="auto"`
- [ ] 设置`use_cache=False`
- [ ] 加载前运行`gc.collect()`

### 推理时：
- [ ] 限制`max_new_tokens`（推荐256或更少）
- [ ] 推理后释放tensor
- [ ] 每10个样本调用一次`torch.cuda.empty_cache()`

### 评估时：
- [ ] 减少评估样本数（50-100个足够）
- [ ] 使用tqdm显示进度（知道还要多久）
- [ ] OOM时立即停止，不要继续运行

---

## 🆘 应急方案

### 如果仍然OOM：

**方案1：更激进的量化**
```python
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    load_in_4bit=True,  # 4-bit，更激进
    device_map="auto",
)
# 预计内存：2-3GB
```

**方案2：减少序列长度**
```python
# 限制输入长度
max_length = 256  # 原来512

inputs = tokenizer(
    prompt, 
    return_tensors="pt",
    max_length=max_length,
    truncation=True
)
```

**方案3：CPU推理（最后手段）**
```python
# 加载到CPU
model = model.to("cpu")

# 推理时
inputs = tokenizer(prompt, return_tensors="pt")  # CPU上
outputs = model.generate(**inputs)  # 在CPU上运行

# 缺点：非常慢（秒级 → 分钟级）
```

**方案4：使用更小的模型**
```python
# 改为7B改为3B（内存占用减一半）
BASE_MODEL = "codellama/CodeLlama-3b-Instruct-hf"

# 但要确保训练时也用的是3B
```

---

## 📈 性能调优

### 内存 vs 性能权衡：

| 设置 | 内存 | 速度 | 质量 | 推荐 |
|------|------|------|------|------|
| float32 | ❌ | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ❌ 不适合Colab |
| float16 | ⚠️ | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ✅ A100/H100 |
| **8-bit** | ✅ | ⚡⚡ | ⭐⭐⭐⭐⭐ | **✅ T4推荐** |
| 4-bit | ✅ | ⚡ | ⭐⭐⭐⭐ | ✅ 显存很紧 |
| CPU推理 | ✅✅ | 🐢 | ⭐⭐⭐⭐⭐ | ❌ 太慢 |

---

## 🔍 监控内存用量

### Colab中实时监控：
```python
import psutil
import torch

# 系统内存
mem = psutil.virtual_memory()
print(f"系统: {mem.available/1024**3:.1f}GB 可用")

# GPU内存
print(f"GPU: {torch.cuda.memory_allocated()/1024**3:.1f}GB 已用")
print(f"GPU: {torch.cuda.memory_reserved()/1024**3:.1f}GB 保留")

# 可视化（GPU）
!nvidia-smi
```

---

## 常见错误和解决方案

### Error 1: "CUDA out of memory"
```
RuntimeError: CUDA out of memory. Tried to allocate X.XX GiB
```
**原因**：单个操作超过显存
**修复**：
1. 减少batch_size（推理中通常是1）
2. 减少max_length或max_new_tokens
3. 启用8-bit或4-bit量化

### Error 2: "Model file not found"
```
FileNotFoundError: /content/drive/MyDrive/gis-models/...
```
**原因**：模型没有保存到Google Drive
**检查**：
```python
import os
path = "/content/drive/MyDrive/gis-models/codellama-gis-lora"
os.listdir(path)  # 看看有什么文件
```

### Error 3: Kernel crash（直接重启，没有错误信息）
```
Your session crashed after X minutes
```
**原因**：系统内存（RAM）用完了，不仅仅是GPU显存
**原因2**：某个操作导致无法恢复的内存泄漏
**修复**：
1. 重启kernel
2. 减少样本数
3. 确保正确调用了cleanup代码

---

## 📚 参考资源

- [Hugging Face Transformers - Memory Efficient Inference](https://huggingface.co/docs/transformers/perf_infer_gpu_one)
- [PEFT - 8-bit Quantization](https://github.com/huggingface/peft)
- [bitsandbytes Documentation](https://github.com/TimDettmers/bitsandbytes)
- [Colab GPU配置](https://colab.research.google.com/?utm_source=scs-index)

---

## 🎯 总结

**推荐的Colab最小配置：**
- ✅ Runtime: T4 GPU（免费）或A100（Pro）
- ✅ 模型加载: `load_in_8bit=True, device_map="auto"`
- ✅ 推理设置: `max_new_tokens=256`
- ✅ 评估样本: 50-100个
- ✅ 其他: 定期调用`gc.collect()`和`torch.cuda.empty_cache()`

**预期性能：**
- 模型加载时间：1-2分钟
- 单个推理时间：3-5秒（8-bit）
- 50个样本完整评估：3-5分钟

**如果仍然OOM：**
1. 重启kernel
2. 启用4-bit量化
3. 减少评估样本到10-20个
4. 使用更小的模型（3B而不是7B）

---

最后更新：2026年1月
