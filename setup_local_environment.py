#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_local_environment.py - 本地环境初始化脚本

这个脚本用于将 Colab 训练好的模型本地化，包括：
1. 从 Colab 下载模型
2. 配置本地环境
3. 验证所有依赖
4. 生成本地配置文件

使用方法：
    python setup_local_environment.py
"""

import os
import json
import sys
from pathlib import Path
import subprocess
import shutil

# ============================================================
# 配置
# ============================================================

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 本地模型存储目录
LOCAL_MODELS_DIR = PROJECT_ROOT / "models"
LOCAL_MODEL_PATH = LOCAL_MODELS_DIR / "step-level-model-865"

# RAG 索引目录
RAG_INDEX_DIR = PROJECT_ROOT / "data" / "processed" / "rag_index"

# 配置文件
CONFIG_FILE = PROJECT_ROOT / "configs" / "local_config.json"

# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG = {
    "model": {
        "base_model": "codellama/CodeLlama-7b-Instruct-hf",
        "local_path": str(LOCAL_MODEL_PATH),
        "lora_r": 64,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "device": "auto",  # "cuda", "cpu", "mps"
        "torch_dtype": "float16",  # "float16", "float32"
    },
    "rag": {
        "enabled": True,
        "index_path": str(RAG_INDEX_DIR),
        "model": "all-MiniLM-L6-v2",
        "threshold": 0.8,
    },
    "inference": {
        "max_tokens": 1024,
        "temperature": 0.7,
        "top_p": 0.95,
        "batch_size": 4,
    },
    "environment": {
        "python_version": "3.10+",
        "cuda_version": "11.8+",  # 可选
        "cudnn_version": "8.0+",   # 可选
    }
}

# ============================================================
# 颜色输出
# ============================================================

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}  {text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")

def print_ok(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_warn(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_fail(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.OKBLUE}ℹ️  {text}{Colors.ENDC}")

def print_section(text):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}→ {text}{Colors.ENDC}")

# ============================================================
# 主要函数
# ============================================================

def check_python_version():
    """检查 Python 版本"""
    print_section("检查 Python 版本")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 9:
        print_ok(f"Python 版本: {version_str}")
        return True
    else:
        print_fail(f"Python 版本过低: {version_str}，需要 3.9+")
        return False

def check_cuda():
    """检查 CUDA 支持"""
    print_section("检查 CUDA/GPU 支持")
    
    try:
        import torch
        if torch.cuda.is_available():
            print_ok(f"GPU 可用: {torch.cuda.get_device_name(0)}")
            print_info(f"CUDA 版本: {torch.version.cuda}")
            print_info(f"GPU 内存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
            return True
        else:
            print_warn("GPU 不可用，将使用 CPU 推理（会很慢）")
            return False
    except Exception as e:
        print_warn(f"检查 GPU 失败: {e}")
        return False

def create_directories():
    """创建必要的目录"""
    print_section("创建目录结构")
    
    dirs = [
        LOCAL_MODELS_DIR,
        LOCAL_MODEL_PATH,
        CONFIG_FILE.parent,
    ]
    
    for dir_path in dirs:
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print_ok(f"创建目录: {dir_path}")
        else:
            print_info(f"目录已存在: {dir_path}")

def create_config_file():
    """创建本地配置文件"""
    print_section("生成本地配置文件")
    
    config_path = PROJECT_ROOT / "configs" / "local_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    
    print_ok(f"配置文件已生成: {config_path}")
    return config_path

def check_dependencies():
    """检查依赖包"""
    print_section("检查依赖包")
    
    required_packages = [
        'torch',
        'transformers',
        'peft',
        'numpy',
        'tqdm',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print_ok(f"{package}")
        except ImportError:
            print_fail(f"{package} (未安装)")
            missing.append(package)
    
    if missing:
        print_warn(f"\n缺少 {len(missing)} 个包，请运行:")
        print(f"  pip install {' '.join(missing)}")
        return False
    else:
        print_ok("所有依赖包已安装")
        return True

def download_base_model():
    """下载基础模型"""
    print_section("下载基础模型")
    
    base_model = DEFAULT_CONFIG["model"]["base_model"]
    print_info(f"基础模型: {base_model}")
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        print_info("下载 Tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(base_model)
        print_ok("Tokenizer 下载完成")
        
        print_info("下载模型（这可能需要 10-30 分钟）...")
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            device_map="auto",
            load_in_8bit=True,
        )
        print_ok("模型下载完成")
        
        return True
    except Exception as e:
        print_fail(f"下载失败: {e}")
        return False

def create_inference_script():
    """创建本地推理脚本"""
    print_section("创建本地推理脚本")
    
    script_path = PROJECT_ROOT / "local_inference.py"
    
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
local_inference.py - 本地推理脚本

使用本地保存的模型进行推理，无需 Colab。

使用方法：
    python local_inference.py --instruction "Your instruction here"
"""

import argparse
import json
from pathlib import Path
from src.inference import HybridInferencer


def main():
    parser = argparse.ArgumentParser(description="本地模型推理")
    parser.add_argument("--instruction", type=str, required=True, help="输入指令")
    parser.add_argument("--model-path", type=str, default="./models/step-level-model-865", help="模型路径")
    parser.add_argument("--rag-path", type=str, default="./data/processed/rag_index", help="RAG 索引路径")
    parser.add_argument("--threshold", type=float, default=0.8, help="RAG 相似度阈值")
    parser.add_argument("--output-json", action="store_true", help="输出为 JSON 格式")
    
    args = parser.parse_args()
    
    print("🚀 本地推理引擎启动中...")
    
    # 初始化推理引擎
    try:
        inferencer = HybridInferencer(
            model_path=args.model_path,
            rag_index_path=args.rag_path,
            use_rag=True,
            device="auto"
        )
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        print("\\n💡 故障排查:")
        print("  1. 检查模型路径是否正确")
        print("  2. 检查 RAG 索引是否存在")
        print("  3. 检查依赖是否完整")
        return
    
    print(f"✅ 推理引擎已就绪\\n")
    
    # 执行推理
    print(f"📝 输入指令: {args.instruction}")
    print("⏳ 推理中...\n")
    
    try:
        result = inferencer.infer(
            args.instruction,
            rag_threshold=args.threshold,
            return_details=True
        )
        
        # 显示结果
        if args.output_json:
            # JSON 格式输出
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # 友好格式输出
            print("="*70)
            print("🎯 推理结果")
            print("="*70)
            print(f"\\n📊 数据源: {result['source'].upper()}")
            print(f"📈 置信度: {result['confidence']:.4f}")
            print(f"📝 说明: {result['explanation']}")
            
            if isinstance(result['result'], dict):
                print("\\n📤 结构化结果:")
                print(json.dumps(result['result'], indent=2, ensure_ascii=False))
            else:
                print(f"\\n📤 结果: {result['result']}")
            
            print(f"\\n{'='*70}")
    
    except Exception as e:
        print(f"❌ 推理失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置可执行权限（Unix-like 系统）
    script_path.chmod(0o755)
    
    print_ok(f"推理脚本已创建: {script_path}")
    print_info(f"使用方法: python {script_path} --instruction 'Your instruction'")

def create_docker_files():
    """创建 Docker 部署文件"""
    print_section("创建 Docker 配置")
    
    # Dockerfile
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    dockerfile_content = '''FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# 安装 Python 和依赖
RUN apt-get update && apt-get install -y \\
    python3.10 python3.10-dev python3-pip \\
    git curl wget \\
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露端口（如果运行 API 服务）
EXPOSE 5000

# 默认命令
CMD ["python3", "local_inference.py", "--help"]
'''
    
    with open(dockerfile_path, 'w', encoding='utf-8') as f:
        f.write(dockerfile_content)
    
    print_ok(f"Dockerfile 已创建: {dockerfile_path}")
    
    # docker-compose.yml
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    compose_content = '''version: '3.8'

services:
  gis-inference:
    build: .
    image: gis-inference:latest
    container_name: gis-inference
    volumes:
      - ./models:/app/models
      - ./data:/app/data
    environment:
      - CUDA_VISIBLE_DEVICES=0
    ports:
      - "5000:5000"
    command: python3 local_inference.py --instruction "example"
'''
    
    with open(compose_path, 'w', encoding='utf-8') as f:
        f.write(compose_content)
    
    print_ok(f"docker-compose.yml 已创建: {compose_path}")

def create_setup_guide():
    """创建本地化设置指南"""
    print_section("创建本地化指南")
    
    guide_path = PROJECT_ROOT / "docs" / "LOCAL_SETUP.md"
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    
    guide_content = '''# 🖥️ 本地模型部署指南

本指南帮助您在本地机器上部署 GIS 模型，无需 Colab。

## 📋 系统要求

### 最低配置
- Python 3.9+
- 内存: 16GB+
- 磁盘: 50GB+ (用于模型存储)

### 推荐配置
- Python 3.10+
- NVIDIA GPU (推荐 12GB+ VRAM)
- CUDA 11.8+
- 内存: 32GB+
- 磁盘: 100GB+ (SSD)

## 🚀 快速开始

### 第 1 步: 克隆项目

```bash
git clone <your-repo-url>
cd gis-code-ai
```

### 第 2 步: 创建虚拟环境

```bash
# Python venv
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\\Scripts\\activate  # Windows

# 或使用 conda
conda create -n gis python=3.10
conda activate gis
```

### 第 3 步: 安装依赖

```bash
pip install -r requirements.txt
```

### 第 4 步: 初始化本地环境

```bash
python setup_local_environment.py
```

这个脚本会：
- ✅ 检查 Python 版本
- ✅ 检查 GPU 支持
- ✅ 创建目录结构
- ✅ 生成配置文件
- ✅ 下载基础模型

### 第 5 步: 下载已训练的 LoRA 权重

**方式 1: 从 Google Drive**

```bash
# 下载模型到 ./models/step-level-model-865/
# 确保包含以下文件:
# - adapter_config.json
# - adapter_model.bin 或 model.safetensors
# - training_info.json
```

**方式 2: 从 Hugging Face** (如果已上传)

```bash
huggingface-cli download <your-username>/<model-name> --local-dir ./models/step-level-model-865
```

## 💻 使用模型

### 方式 1: 命令行推理

```bash
python local_inference.py --instruction "Open the editor"
```

输出:
```
========================================
🎯 推理结果
========================================

📊 数据源: RAG
📈 置信度: 0.8547
📝 说明: RAG 检索 (相似度: 0.8547) → 超过阈值 0.8，直接返回 RAG 结果

📤 结构化结果:
{
  "module": "Editor(s)",
  "method": "Open Object",
  ...
}
```

### 方式 2: Python 脚本

```python
from src.inference import HybridInferencer

# 初始化
inferencer = HybridInferencer(
    model_path="./models/step-level-model-865",
    rag_index_path="./data/processed/rag_index"
)

# 推理
result = inferencer.infer(
    "Open E MS Installatie",
    rag_threshold=0.8
)

print(f"来源: {result['source']}")
print(f"结果: {result['result']}")
```

### 方式 3: Flask API 服务

```bash
# 启动 API 服务
python api_server.py

# 另一个终端调用
curl -X POST http://localhost:5000/api/infer \\
  -H "Content-Type: application/json" \\
  -d '{"instruction": "Open the editor"}'
```

## 🔧 配置文件

编辑 `configs/local_config.json` 以自定义设置：

```json
{
  "model": {
    "device": "cuda",  # "cuda", "cpu", "mps"
    "torch_dtype": "float16",  # "float16", "float32"
    "lora_r": 64
  },
  "rag": {
    "enabled": true,
    "threshold": 0.8
  },
  "inference": {
    "max_tokens": 1024
  }
}
```

## 🐛 故障排查

### 问题 1: 找不到模型文件

```
❌ FileNotFoundError: Model not found at ./models/step-level-model-865
```

**解决:**
1. 检查模型文件是否已下载
2. 确认路径是否正确
3. 运行 `python setup_local_environment.py` 重新初始化

### 问题 2: GPU 内存不足

```
❌ RuntimeError: CUDA out of memory
```

**解决:**
- 编辑 `configs/local_config.json`，设置 `torch_dtype` 为 `float32`
- 或使用 CPU 模式: `device: "cpu"`
- 或降低 batch size

### 问题 3: 推理很慢

**原因:** 使用了 CPU 推理

**解决:**
- 安装 NVIDIA CUDA 和 cuDNN
- 检查 GPU 是否被正确识别: `python -c "import torch; print(torch.cuda.is_available())"`

### 问题 4: 依赖版本冲突

```
❌ ImportError: version conflict
```

**解决:**
```bash
# 重新创建虚拟环境
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🐳 Docker 部署

### 构建 Docker 镜像

```bash
docker build -t gis-inference:latest .
```

### 运行容器

```bash
docker run --gpus all \\
  -v $(pwd)/models:/app/models \\
  -v $(pwd)/data:/app/data \\
  gis-inference:latest \\
  python local_inference.py --instruction "Your instruction"
```

### 使用 Docker Compose

```bash
docker-compose up -d
```

## 📊 性能优化

### 1. 启用量化

```python
from src.inference import HybridInferencer

inferencer = HybridInferencer(
    model_path="./models/step-level-model-865",
    torch_dtype=torch.float32  # 比 float16 更稳定但更慢
)
```

### 2. 使用批量推理

```python
instructions = ["Open editor", "Create cable", ...]
results = inferencer.batch_infer(instructions)
```

### 3. 启用缓存

```python
# 为 RAG 结果缓存
# 为模型预热
```

## 🔒 安全性

### 建议做法

1. **不要提交模型文件** - 添加到 `.gitignore`
   ```
   models/
   data/
   .env
   ```

2. **使用环境变量** 配置敏感信息
   ```python
   import os
   model_path = os.getenv("MODEL_PATH", "./models/step-level-model-865")
   ```

3. **定期更新依赖**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

## 📈 进阶用法

### 自定义模型参数

```python
from src.inference.hybrid_inference import HybridInferencer

inferencer = HybridInferencer(
    model_path="./models/your-model",
    rag_index_path="./data/your-rag",
    device="cuda",
    torch_dtype=torch.float16
)

# 调整推理参数
result = inferencer.infer(
    "Your instruction",
    rag_threshold=0.85,  # 更严格的 RAG 阈值
    top_k=3,             # 返回更多候选
    max_tokens=2048,     # 更长的输出
    return_details=True  # 获取详细信息
)
```

### 监控推理性能

```python
import time

start = time.time()
result = inferencer.infer("Your instruction")
elapsed = time.time() - start

print(f"推理耗时: {elapsed:.2f}s")
print(f"数据源: {result['source']}")
print(f"置信度: {result['confidence']:.4f}")
```

## 🆘 获取帮助

- 📖 查看完整文档: [README.md](../README.md)
- 🚀 快速参考: [QUICK_REFERENCE.md](../docs/QUICK_REFERENCE.md)
- 💬 提交 Issue: GitHub Issues
- 📧 联系支持: support@example.com

---

**最后更新:** 2026-05-01
**版本:** v1.0.0
'''
    
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print_ok(f"本地化指南已创建: {guide_path}")

def create_requirements_local():
    """创建本地环境的 requirements.txt"""
    print_section("创建本地 requirements.txt")
    
    req_path = PROJECT_ROOT / "requirements-local.txt"
    req_content = '''# Core PyTorch (choose one based on your system)
# For GPU (NVIDIA CUDA 11.8)
torch==2.1.0
# torch-cuda-11.8 is installed with torch on Linux/Mac

# For CPU only (uncomment if no GPU)
# torch==2.1.0

# Core dependencies
transformers==4.36.0
peft==0.7.0
numpy==1.24.3
tqdm==4.66.0

# Inference
sentence-transformers==2.2.2
safetensors==0.4.0

# Optional: For model quantization
bitsandbytes==0.41.0  # For 8-bit quantization
accelerate==0.24.0    # For model acceleration

# API/Serving (optional, only if running as service)
flask==2.3.0
flask-cors==4.0.0
gunicorn==21.0.0

# Development tools
jupyter==1.0.0
notebook==7.0.0
ipython==8.16.0

# Monitoring (optional)
tensorboard==2.14.0
# wandb==0.16.0

# Utilities
python-dotenv==1.0.0
click==8.1.7
rich==13.6.0
'''
    
    with open(req_path, 'w', encoding='utf-8') as f:
        f.write(req_content)
    
    print_ok(f"本地 requirements 已创建: {req_path}")

def print_summary():
    """打印总结"""
    print_header("✅ 本地化设置完成!")
    
    print(f"\n{Colors.BOLD}📂 项目结构:{Colors.ENDC}")
    print(f"  models/")
    print(f"    └── step-level-model-865/      # 本地模型存储位置")
    print(f"  data/")
    print(f"    └── processed/")
    print(f"        └── rag_index/            # RAG 索引")
    print(f"  configs/")
    print(f"    └── local_config.json         # 本地配置文件")
    print(f"  local_inference.py              # 本地推理脚本")
    print(f"  Dockerfile                      # Docker 部署")
    print(f"  docker-compose.yml              # Docker Compose 配置")
    print(f"  docs/LOCAL_SETUP.md             # 详细设置指南")
    
    print(f"\n{Colors.BOLD}🚀 后续步骤:{Colors.ENDC}")
    print(f"  1. 下载已训练的 LoRA 权重到 models/step-level-model-865/")
    print(f"  2. 确保 RAG 索引存在于 data/processed/rag_index/")
    print(f"  3. 运行: python local_inference.py --instruction 'Your instruction'")
    print(f"  4. 或阅读 docs/LOCAL_SETUP.md 了解更多使用方法")
    
    print(f"\n{Colors.BOLD}📚 文档:{Colors.ENDC}")
    print(f"  - 本地部署指南: docs/LOCAL_SETUP.md")
    print(f"  - 快速参考: docs/QUICK_REFERENCE.md")
    print(f"  - 完整 API: src/inference/README.md")
    
    print(f"\n{Colors.BOLD}💡 提示:{Colors.ENDC}")
    print(f"  • 编辑 configs/local_config.json 调整模型参数")
    print(f"  • 使用 GPU: 确保 CUDA/NVIDIA 驱动已安装")
    print(f"  • 使用 Docker: docker build -t gis:latest . && docker run gis:latest")
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✨ 祝您使用愉快!{Colors.ENDC}\n")


# ============================================================
# 主程序
# ============================================================

def main():
    print_header("🖥️ 本地模型环境初始化")
    
    all_ok = True
    
    # 检查 Python 版本
    all_ok &= check_python_version()
    
    # 检查 GPU
    check_cuda()
    
    # 创建目录
    create_directories()
    
    # 检查依赖
    all_ok &= check_dependencies()
    
    if not all_ok:
        print_warn("\n⚠️  请先安装缺失的依赖:")
        print("    pip install -r requirements-local.txt")
        sys.exit(1)
    
    # 创建配置文件
    create_config_file()
    
    # 创建推理脚本
    create_inference_script()
    
    # 创建 Docker 配置
    create_docker_files()
    
    # 创建本地化指南
    create_setup_guide()
    
    # 创建本地 requirements
    create_requirements_local()
    
    # 打印总结
    print_summary()


if __name__ == "__main__":
    main()
