# 🖥️ 完整本地化部署指南

## 📋 目录

1. [系统要求](#系统要求)
2. [快速开始](#快速开始-5-分钟)
3. [详细步骤](#详细部署步骤)
4. [使用方法](#使用方法)
5. [故障排查](#故障排查)
6. [生产部署](#生产部署)
7. [性能优化](#性能优化)

---

## 系统要求

### 最低配置

| 组件 | 要求 | 备注 |
|------|------|------|
| **操作系统** | Linux / macOS / Windows | 推荐 Linux |
| **Python** | 3.9+ | 推荐 3.10+ |
| **CPU** | 4 核 | 最低配置 |
| **内存** | 16 GB | 建议 32 GB |
| **磁盘** | 50 GB | 用于模型存储 |
| **GPU** | 可选 | NVIDIA 12GB+ VRAM 推荐 |

### 推荐配置

| 组件 | 推荐 |
|------|------|
| **CPU** | AMD Ryzen 7+ / Intel i7+ |
| **内存** | 32-64 GB |
| **GPU** | NVIDIA RTX 3090 / A100 (24GB+) |
| **磁盘** | SSD 100GB+ |
| **显驱** | NVIDIA CUDA 11.8+ |

### GPU 支持 (可选但推荐)

如果要使用 GPU 加速：

```bash
# NVIDIA GPU 检查
nvidia-smi

# 如果未安装，需要：
# 1. 安装 NVIDIA 驱动 (470+)
# 2. 安装 CUDA Toolkit (11.8+)
# 3. 安装 cuDNN (8.0+)
```

---

## 快速开始 (5 分钟)

### 第 1 步: 克隆项目

```bash
git clone <your-repo-url>
cd gis-code-ai
```

### 第 2 步: 创建虚拟环境

**使用 Python venv:**

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**或使用 Conda:**

```bash
conda create -n gis python=3.10
conda activate gis
```

### 第 3 步: 安装依赖

```bash
pip install -r requirements-local.txt
```

### 第 4 步: 初始化环境

```bash
python setup_local_environment.py
```

这会自动：
- ✅ 检查 Python 版本
- ✅ 检查 GPU 支持
- ✅ 创建必要目录
- ✅ 生成配置文件
- ✅ 下载基础模型

### 第 5 步: 测试推理

```bash
python local_inference.py --instruction "Open the editor"
```

**成功输出示例:**

```
======================================================================
  🚀 GIS 本地推理系统
======================================================================

  📂 加载配置...
  🔧 初始化推理引擎...
  📝 输入指令:
     Open the editor

  ⏳ 推理中...

  ==================================================================
  🎯 推理结果
  ==================================================================

  📊 数据源: RAG
  📈 置信度: 0.8547
  📝 说明: RAG 检索 → 超过阈值，返回 RAG 结果

  📤 结构化结果:
     • module: Editor(s)
     • method: Open Object
     • object: E MS Installatie
     ...

  ==================================================================
```

✅ **恭喜！您已成功本地化模型！**

---

## 详细部署步骤

### 步骤 1: 下载已训练的模型

#### 方式 A: 从 Google Drive

1. 进入你的 Colab 文件夹
2. 右键点击 `step-level-model-865` 文件夹
3. 选择 "下载" 
4. 解压到 `./models/step-level-model-865/`

文件夹应包含：

```
models/
└── step-level-model-865/
    ├── adapter_config.json      ✅ 必须
    ├── adapter_model.bin        ✅ 必须
    ├── model.safetensors        ✅ 或这个
    ├── training_info.json       ✅ 建议
    ├── tokenizer_config.json    ℹ️ 可选
    └── special_tokens_map.json  ℹ️ 可选
```

#### 方式 B: 从 Hugging Face (如果已上传)

```bash
# 安装 huggingface-cli
pip install huggingface-hub

# 下载模型
huggingface-cli download <your-username>/gis-model-865 \
  --local-dir ./models/step-level-model-865 \
  --local-dir-use-symlinks False
```

#### 方式 C: 从云存储 (AWS S3, Azure Blob 等)

```bash
# AWS S3 示例
aws s3 cp s3://your-bucket/gis-model-865 ./models/step-level-model-865 --recursive
```

### 步骤 2: 验证 RAG 索引

确保 RAG 索引存在：

```bash
ls -la data/processed/rag_index/

# 应该看到:
# -rw-r--r-- embeddings.npy      (2.0M)
# -rw-r--r-- metadata.jsonl      (10M)
```

如果不存在，需要重新生成：

```bash
python scripts/02_build_rag.py
```

### 步骤 3: 验证数据文件

检查必要的数据文件：

```bash
# 检查训练数据
ls -la data/processed/
  ✅ file_level_data.jsonl
  ✅ file_level_instructions.jsonl
  ✅ step_level_data.jsonl
  ✅ step_level_instructions.jsonl
  ✅ rag_index/
```

### 步骤 4: 配置本地参数

编辑 `configs/local_config.json`:

```json
{
  "model": {
    "base_model": "codellama/CodeLlama-7b-Instruct-hf",
    "local_path": "./models/step-level-model-865",
    "device": "cuda",           # "cuda", "cpu", "mps"
    "torch_dtype": "float16"    # "float16", "float32"
  },
  "rag": {
    "enabled": true,
    "index_path": "./data/processed/rag_index",
    "threshold": 0.8
  },
  "inference": {
    "max_tokens": 1024
  },
  "api": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false
  }
}
```

### 步骤 5: 测试连接

```bash
# 测试模型加载
python -c "
from src.inference import HybridInferencer
inferencer = HybridInferencer(
    model_path='./models/step-level-model-865',
    rag_index_path='./data/processed/rag_index'
)
print('✅ 模型加载成功')
"

# 输出:
# ✅ 模型加载成功
```

---

## 使用方法

### 方式 1: 命令行工具

#### 单条推理

```bash
# 基础用法
python local_inference.py --instruction "Open the editor"

# 自定义参数
python local_inference.py \
  --instruction "Create a new cable" \
  --threshold 0.7 \
  --max-tokens 2048

# 输出 JSON 格式
python local_inference.py \
  --instruction "Open editor" \
  --output-json
```

#### 批量推理

**创建 instructions.json:**

```json
[
  "Open the editor",
  "Create a new cable",
  "Switch to geographical view"
]
```

**执行批量推理:**

```bash
python local_inference.py --batch-file instructions.json
```

**输出:**

```
  ==================================================================
  📊 批量推理统计
  ==================================================================
    • 总数: 3
    • RAG 命中: 2 (66.7%)
    • 模型推理: 1 (33.3%)
  ==================================================================
```

#### 交互模式

```bash
# 启动交互模式（无参数）
python local_inference.py

# 输入指令进行推理，输入 'quit' 退出
📝 请输入指令: Open the editor
  [结果...]

📝 请输入指令: quit
  👋 再见!
```

### 方式 2: Python 脚本

```python
from src.inference import HybridInferencer

# 初始化 (1 次)
inferencer = HybridInferencer(
    model_path="./models/step-level-model-865",
    rag_index_path="./data/processed/rag_index",
    use_rag=True,
    device="cuda"  # 或 "cpu"
)

# 单条推理
result = inferencer.infer(
    "Open E MS Installatie",
    rag_threshold=0.8,
    return_details=True
)

print(f"来源: {result['source']}")           # "rag" 或 "model"
print(f"置信度: {result['confidence']:.4f}") # 相似度或 1.0
print(f"结果: {result['result']}")           # JSON 输出
print(f"说明: {result['explanation']}")      # 处理过程

# 批量推理
instructions = [
    "Open editor",
    "Create cable",
    "Delete object"
]

results = inferencer.batch_infer(
    instructions,
    rag_threshold=0.8
)

for result in results:
    print(f"{result['instruction']} → {result['source']}")
```

### 方式 3: Flask API 服务

#### 启动服务器

```bash
python api_server.py
```

**输出:**

```
======================================================================
  🚀 GIS 推理 API 服务器
======================================================================

  ✅ 服务器信息:
     • 地址: http://0.0.0.0:5000
     • API 文档: http://0.0.0.0:5000/api/docs
     • 健康检查: http://0.0.0.0:5000/health

  📚 示例请求:
     curl -X POST http://localhost:5000/api/infer \
       -H 'Content-Type: application/json' \
       -d '{"instruction": "Open the editor"}'

  ======================================================================
  按 Ctrl+C 停止服务器
```

#### 调用 API

**健康检查:**

```bash
curl http://localhost:5000/health
```

**单条推理:**

```bash
curl -X POST http://localhost:5000/api/infer \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Open the editor",
    "threshold": 0.8,
    "return_details": true
  }'
```

**响应:**

```json
{
  "status": "success",
  "instruction": "Open the editor",
  "source": "rag",
  "confidence": 0.8547,
  "result": {
    "module": "Editor(s)",
    "method": "Open Object",
    "object": "E MS Installatie",
    ...
  },
  "explanation": "RAG 检索 (相似度: 0.8547) → 超过阈值 0.8，直接返回 RAG 结果",
  "timestamp": "2026-05-01T12:34:56.789012"
}
```

**批量推理:**

```bash
curl -X POST http://localhost:5000/api/batch \
  -H "Content-Type: application/json" \
  -d '{
    "instructions": [
      "Open editor",
      "Create cable",
      "Delete object"
    ],
    "threshold": 0.8
  }'
```

**API 文档:**

```bash
curl http://localhost:5000/api/docs | jq
```

### 方式 4: Docker 容器 (推荐用于部署)

#### 构建镜像

```bash
docker build -t gis-inference:latest .
```

#### 运行容器

**交互模式:**

```bash
docker run -it \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/data:/app/data \
  gis-inference:latest \
  python local_inference.py --instruction "Open editor"
```

**API 服务模式:**

```bash
docker run -d \
  --name gis-api \
  -p 5000:5000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/data:/app/data \
  --gpus all \
  gis-inference:latest \
  python api_server.py
```

**使用 Docker Compose:**

```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

**GPU 支持:**

```bash
# 需要 nvidia-docker
docker run --gpus all -it gis-inference:latest python local_inference.py
```

---

## 故障排查

### ❌ 模型找不到

**错误:**

```
FileNotFoundError: Model not found at ./models/step-level-model-865
```

**解决:**

1. 检查模型文件是否已下载
   ```bash
   ls -la ./models/step-level-model-865/
   ```

2. 检查是否包含关键文件
   ```bash
   # 必须有以下至少一个:
   ls adapter_config.json
   ls model.safetensors
   ```

3. 重新下载模型或检查路径

### ❌ GPU 内存不足

**错误:**

```
RuntimeError: CUDA out of memory. Tried to allocate X.XX GiB
```

**解决:**

```json
// 编辑 configs/local_config.json
{
  "model": {
    "torch_dtype": "float32",  // 从 float16 改为 float32
    "device": "cpu"            // 或改为 CPU
  }
}
```

**或使用 CPU:**

```bash
python local_inference.py --instruction "..." --device cpu
```

### ❌ 推理很慢

**原因:** 使用了 CPU 推理

**解决:** 安装 GPU 驱动

```bash
# 检查 GPU 是否被识别
python -c "import torch; print(torch.cuda.is_available())"

# 输出应该是: True
```

### ❌ 依赖版本冲突

**错误:**

```
ImportError: cannot import name 'xxx'
```

**解决:** 重建虚拟环境

```bash
# 删除旧环境
rm -rf venv

# 创建新环境
python -m venv venv
source venv/bin/activate

# 重新安装
pip install -r requirements-local.txt

# 重新初始化
python setup_local_environment.py
```

### ❌ API 端口被占用

**错误:**

```
Address already in use
```

**解决:**

```bash
# 方法 1: 改用其他端口
python api_server.py --port 5001

# 方法 2: 杀死占用端口的进程
# Linux/macOS:
lsof -ti:5000 | xargs kill -9

# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

---

## 生产部署

### 部署架构

```
┌─────────────────┐
│   用户请求       │
└────────┬────────┘
         │ HTTP/HTTPS
         ↓
┌─────────────────┐
│  Nginx 反向代理  │ (可选)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Gunicorn WSGI  │ (Flask 应用服务器)
│  (多工作进程)   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Flask 应用      │ (api_server.py)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ 推理引擎        │ (HybridInferencer)
├─────────────────┤
│ • RAG 索引      │
│ • 微调模型      │
└─────────────────┘
```

### 使用 Gunicorn

#### 安装

```bash
pip install gunicorn
```

#### 启动

```bash
gunicorn \
  --workers 4 \
  --worker-class sync \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  api_server:app
```

#### 配置文件 (gunicorn_config.py)

```python
# 工作进程配置
workers = 4
worker_class = 'sync'
worker_connections = 1000
timeout = 120

# 服务器绑定
bind = ['0.0.0.0:5000']

# 日志配置
accesslog = '/var/log/gis-api/access.log'
errorlog = '/var/log/gis-api/error.log'
loglevel = 'info'

# 服务器相关
keepalive = 2
daemon = False
pidfile = '/var/run/gunicorn.pid'
```

### 使用 Nginx 反向代理

#### Nginx 配置

```nginx
upstream gis_api {
    server localhost:5000;
    server localhost:5001;
    server localhost:5002;
}

server {
    listen 80;
    server_name gis-api.example.com;

    # 请求超时
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    location /api/ {
        proxy_pass http://gis_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://gis_api;
    }
}
```

#### 启动

```bash
nginx -s reload
```

### Systemd Service (Linux)

创建 `/etc/systemd/system/gis-api.service`:

```ini
[Unit]
Description=GIS Inference API
After=network.target

[Service]
Type=notify
User=gis-user
WorkingDirectory=/opt/gis-code-ai
Environment="PATH=/opt/gis-code-ai/venv/bin"
ExecStart=/opt/gis-code-ai/venv/bin/gunicorn \
  --workers 4 \
  --bind 0.0.0.0:5000 \
  api_server:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl start gis-api
sudo systemctl enable gis-api
sudo systemctl status gis-api
```

---

## 性能优化

### 1. 启用 GPU 加速

```json
{
  "model": {
    "device": "cuda",
    "torch_dtype": "float16"
  }
}
```

**性能提升:**
- 推理速度: 3-5 倍更快

### 2. 使用量化

```json
{
  "model": {
    "torch_dtype": "float32"  // 相比 float16 更稳定
  }
}
```

### 3. 启用缓存 (计划中)

```python
# 缓存 RAG 结果
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_rag_result(instruction):
    return rag.retrieve(instruction)
```

### 4. 批量推理

```python
# 更高效的批量处理
results = inferencer.batch_infer(
    large_instruction_list,
    rag_threshold=0.8
)
```

### 5. 模型预热

```python
# 在启动时预热模型
print("预热模型中...")
inferencer.infer("test instruction")
print("预热完成")
```

### 6. 监控性能

```bash
# 监控 GPU 使用
watch -n 1 nvidia-smi

# 监控进程
top -p $(pgrep -f python)
```

---

## 总结

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **CLI** | 简单，快速 | 无法并发 | 测试、单次推理 |
| **Python** | 灵活，集成 | 需要编程 | 应用集成 |
| **API** | 跨语言，可扩展 | 网络开销 | 服务化部署 |
| **Docker** | 隔离，便携 | 资源占用 | 容器部署 |

---

## 🆘 获取帮助

| 资源 | 链接 |
|------|------|
| 完整文档 | [../README.md](../README.md) |
| API 参考 | [../src/inference/README.md](../src/inference/README.md) |
| 快速参考 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |
| 提交 Issue | GitHub Issues |

---

**最后更新:** 2026-05-01  
**版本:** v1.0.0  
**状态:** 生产就绪 ✅
