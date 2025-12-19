# 快速开始指南

这是一个简化的快速开始指南，帮助您在 5 分钟内开始使用 GIS Code AI。

## 1. 前提条件

确保已安装：
- Python 3.8 或更高版本
- Git

## 2. 获取代码

```bash
# 如果尚未克隆仓库
git clone https://github.com/rockyistt/gis-code-ai.git
cd gis-code-ai
```

## 3. 设置环境

### 方案 A: 使用虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 方案 B: 不使用虚拟环境

```bash
# 直接安装依赖（不推荐用于生产环境）
pip install -r requirements.txt
```

## 4. 验证安装

### 运行示例代码

```bash
# 设置 PYTHONPATH 并运行示例
export PYTHONPATH=$PWD  # Linux/Mac
# 或
set PYTHONPATH=%CD%  # Windows CMD
# 或
$env:PYTHONPATH = $PWD  # Windows PowerShell

python examples/basic_usage.py
```

如果看到以下输出，说明安装成功：
```
✅ 基本示例运行成功！
📖 查看 SETUP.md 了解更多详细信息
```

### 运行测试（可选）

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行测试
pytest tests/ -v
```

## 5. 下一步

恭喜！您已成功设置 GIS Code AI。现在可以：

1. **查看详细文档**
   - [完整设置指南](SETUP.md) - 详细的配置说明
   - [使用指南](docs/GUIDE.md) - 如何使用各个模块
   - [API 文档](docs/API.md) - API 参考

2. **探索示例**
   ```bash
   cd examples/
   ls -la  # 查看所有示例
   ```

3. **开始编写代码**
   - 在 `src/` 目录中添加您的代码
   - 在 `tests/` 目录中添加测试
   - 在 `examples/` 中创建使用示例

4. **贡献代码**
   - 阅读 [贡献指南](CONTRIBUTING.md)
   - 提交 Pull Request

## 常见问题

### Q: 为什么导入模块失败？

A: 确保设置了 PYTHONPATH：

```bash
export PYTHONPATH=$PWD  # Linux/Mac
```

或者在代码中添加：

```python
import sys
sys.path.insert(0, '/path/to/gis-code-ai')
```

### Q: 如何安装 GIS 相关依赖？

A: 对于 GeoPandas 等 GIS 库，可能需要系统依赖：

```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin libgdal-dev

# macOS
brew install gdal

# Windows - 使用 Conda
conda install -c conda-forge geopandas
```

### Q: 测试失败怎么办？

A: 首先确保安装了测试依赖：

```bash
pip install pytest pytest-cov
```

然后查看具体的错误信息并解决。

## 获取帮助

遇到问题？

1. 查看 [SETUP.md](SETUP.md) 的故障排除部分
2. 查看 [Issues](https://github.com/rockyistt/gis-code-ai/issues)
3. 创建新的 Issue

---

**祝您使用愉快！** 🎉
