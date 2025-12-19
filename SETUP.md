# GIS 代码 AI 仓库设置指南

本指南将帮助您从头开始创建和配置 GIS 测试自动化项目仓库。

## 目录

1. [前置要求](#前置要求)
2. [初始化仓库](#初始化仓库)
3. [项目结构](#项目结构)
4. [环境配置](#环境配置)
5. [依赖安装](#依赖安装)
6. [开始开发](#开始开发)

## 前置要求

在开始之前，请确保您的系统已安装以下工具：

### 必需工具
- **Git** (>= 2.30): 版本控制工具
  ```bash
  git --version
  ```

- **Python** (>= 3.8): 主要编程语言
  ```bash
  python --version
  # 或
  python3 --version
  ```

- **pip**: Python 包管理器
  ```bash
  pip --version
  ```

### 推荐工具
- **Visual Studio Code** 或其他代码编辑器
- **Docker** (可选): 用于容器化部署
- **虚拟环境工具**: venv 或 conda

## 初始化仓库

### 1. 创建本地仓库

如果您还没有克隆此仓库，请执行：

```bash
# 克隆仓库
git clone https://github.com/rockyistt/gis-code-ai.git
cd gis-code-ai
```

如果从零开始创建：

```bash
# 创建项目目录
mkdir gis-code-ai
cd gis-code-ai

# 初始化 Git 仓库
git init

# 创建 README
echo "# gis-code-ai" > README.md
echo "AI自动化在GIS测试方面的应用" >> README.md

# 首次提交
git add README.md
git commit -m "Initial commit"
```

### 2. 连接远程仓库

```bash
# 添加远程仓库
git remote add origin https://github.com/rockyistt/gis-code-ai.git

# 推送到远程
git branch -M main
git push -u origin main
```

## 项目结构

建议的项目目录结构：

```
gis-code-ai/
├── .github/                 # GitHub 配置
│   └── workflows/          # CI/CD 工作流
│       └── test.yml
├── docs/                   # 文档目录
│   ├── api.md             # API 文档
│   └── guide.md           # 使用指南
├── src/                    # 源代码目录
│   ├── __init__.py
│   ├── core/              # 核心功能模块
│   │   ├── __init__.py
│   │   └── gis_processor.py
│   ├── ai/                # AI 相关模块
│   │   ├── __init__.py
│   │   └── model.py
│   └── utils/             # 工具函数
│       ├── __init__.py
│       └── helpers.py
├── tests/                  # 测试目录
│   ├── __init__.py
│   ├── test_core.py
│   └── test_ai.py
├── examples/              # 示例代码
│   └── basic_usage.py
├── data/                  # 数据目录
│   ├── raw/              # 原始数据
│   └── processed/        # 处理后的数据
├── .gitignore            # Git 忽略文件
├── README.md             # 项目说明
├── SETUP.md              # 本设置指南
├── requirements.txt      # Python 依赖
├── setup.py              # 项目安装配置
└── LICENSE               # 许可证
```

### 创建目录结构

执行以下命令创建推荐的目录结构：

```bash
# 创建主要目录
mkdir -p .github/workflows
mkdir -p docs
mkdir -p src/{core,ai,utils}
mkdir -p tests
mkdir -p examples
mkdir -p data/{raw,processed}

# 创建 __init__.py 文件
touch src/__init__.py
touch src/core/__init__.py
touch src/ai/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
```

## 环境配置

### 1. 创建 Python 虚拟环境

使用虚拟环境可以隔离项目依赖：

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. 创建 .gitignore 文件

创建 `.gitignore` 文件以忽略不需要版本控制的文件：

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# 操作系统
.DS_Store
Thumbs.db

# 项目特定
data/raw/*
data/processed/*
!data/raw/.gitkeep
!data/processed/.gitkeep
*.log
.env

# 测试和覆盖率
.pytest_cache/
.coverage
htmlcov/
```

### 3. 创建 requirements.txt

创建依赖文件，列出项目所需的 Python 包：

```txt
# GIS 相关
geopandas>=0.12.0
shapely>=2.0.0
fiona>=1.9.0
rasterio>=1.3.0

# AI/ML 相关
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
tensorflow>=2.13.0
# 或使用 pytorch
# torch>=2.0.0

# 测试相关
pytest>=7.4.0
pytest-cov>=4.1.0

# 工具
python-dotenv>=1.0.0
requests>=2.31.0
```

## 依赖安装

### 安装 Python 依赖

```bash
# 确保虚拟环境已激活
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 安装开发依赖（可选）
pip install pytest pytest-cov black flake8 mypy
```

### 配置 GIS 环境

GIS 相关的包可能需要额外的系统依赖：

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    libspatialindex-dev
```

#### macOS
```bash
brew install gdal
brew install spatialindex
```

#### Windows
推荐使用 Conda 环境：
```bash
conda install -c conda-forge geopandas
```

## 开始开发

### 1. 创建示例代码

创建一个简单的示例文件 `examples/basic_usage.py`：

```python
"""
GIS AI 基本使用示例
"""
import geopandas as gpd
from pathlib import Path

def main():
    print("欢迎使用 GIS Code AI!")
    print("这是一个 GIS 测试自动化项目")
    
    # 在这里添加您的代码
    
if __name__ == "__main__":
    main()
```

### 2. 编写测试

创建测试文件 `tests/test_core.py`：

```python
"""
核心功能测试
"""
import pytest

def test_example():
    """示例测试"""
    assert True

def test_addition():
    """基本数学测试"""
    assert 1 + 1 == 2
```

运行测试：

```bash
pytest tests/
```

### 3. 配置 CI/CD (可选)

创建 GitHub Actions 工作流 `.github/workflows/test.yml`：

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=src
```

## 下一步

完成基本设置后，您可以：

1. **定义项目需求**: 明确项目的具体目标和功能
2. **设计架构**: 规划代码结构和模块划分
3. **实现核心功能**: 开始编写 GIS 处理和 AI 测试代码
4. **编写文档**: 完善 API 文档和使用指南
5. **添加测试**: 确保代码质量和可靠性
6. **持续集成**: 设置 CI/CD 流程自动化测试和部署

## 常见问题

### Q: GDAL 安装失败怎么办？
A: 尝试使用 Conda 安装：`conda install -c conda-forge gdal`

### Q: 如何更新依赖？
A: 使用 `pip install --upgrade -r requirements.txt`

### Q: 如何贡献代码？
A: 请查看 CONTRIBUTING.md 文件（如果有）

## 需要帮助？

- 查看项目 [Issues](https://github.com/rockyistt/gis-code-ai/issues)
- 提出新的 Issue
- 联系项目维护者

---

**祝您开发顺利！** 🚀
