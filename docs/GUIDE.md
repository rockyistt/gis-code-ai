# 使用指南

## 简介

GIS Code AI 是一个用于 GIS 数据自动化测试和处理的 Python 项目，集成了 AI 技术以提升处理效率。

## 安装

详细的安装说明请查看 [SETUP.md](../SETUP.md)。

### 快速安装

```bash
pip install -r requirements.txt
```

## 基本概念

### GIS 处理器 (GISProcessor)

GIS 处理器负责：
- 加载各种格式的 GIS 数据（Shapefile, GeoJSON 等）
- 数据验证和清洗
- 数据转换和处理

### AI 模型 (AIModel)

AI 模型提供：
- 机器学习能力
- 预测和分类功能
- 模型训练和评估

### 工具函数 (Utils)

提供常用的辅助功能：
- 日志设置
- 文件验证
- 目录管理

## 工作流程

### 1. 数据准备

将 GIS 数据放在 `data/raw/` 目录：

```bash
data/
└── raw/
    ├── my_data.shp
    ├── my_data.shx
    ├── my_data.dbf
    └── my_data.prj
```

### 2. 数据加载和处理

```python
from src.core.gis_processor import GISProcessor

# 创建处理器
processor = GISProcessor()

# 加载数据
processor.load_data("data/raw/my_data.shp")

# 验证数据
if processor.validate():
    # 处理数据
    result = processor.process()
```

### 3. AI 模型训练

```python
from src.ai.model import AIModel
import numpy as np

# 准备训练数据
X_train = np.array([[1, 2], [3, 4], [5, 6]])
y_train = np.array([0, 1, 0])

# 创建和训练模型
model = AIModel(model_type="classification")
model.train(X_train, y_train)

# 保存模型
model.save("models/my_model.pkl")
```

### 4. 预测

```python
# 准备测试数据
X_test = np.array([[2, 3], [4, 5]])

# 加载模型（如果需要）
model.load("models/my_model.pkl")

# 进行预测
predictions = model.predict(X_test)
```

### 5. 评估

```python
# 评估模型
metrics = model.evaluate(X_test, y_test)
print(f"准确率: {metrics['accuracy']}")
```

## 高级功能

### 自定义日志

```python
from src.utils.helpers import setup_logger
import logging

# 创建自定义日志记录器
logger = setup_logger("my_module", level=logging.DEBUG)
logger.debug("这是调试信息")
logger.info("这是普通信息")
logger.warning("这是警告")
logger.error("这是错误")
```

### 批量处理

```python
from pathlib import Path
from src.core.gis_processor import GISProcessor

# 处理目录中的所有文件
data_dir = Path("data/raw")
for file in data_dir.glob("*.shp"):
    processor = GISProcessor()
    processor.load_data(str(file))
    processor.process()
```

## 最佳实践

1. **数据管理**
   - 保持原始数据不变
   - 处理后的数据保存在 `data/processed/`
   - 使用版本控制管理代码，但不要提交大型数据文件

2. **模型管理**
   - 定期保存训练好的模型
   - 记录模型的训练参数和性能指标
   - 使用有意义的模型文件名

3. **日志记录**
   - 在关键步骤添加日志
   - 使用适当的日志级别
   - 定期清理旧日志文件

4. **测试**
   - 为新功能编写测试
   - 运行测试确保代码正确性
   - 保持高测试覆盖率

## 故障排除

### 常见问题

#### GDAL 导入错误
```
ImportError: No module named 'osgeo'
```
**解决方案**: 安装 GDAL
```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin libgdal-dev
pip install gdal

# macOS
brew install gdal
pip install gdal

# Windows
conda install -c conda-forge gdal
```

#### 内存不足
处理大型 GIS 文件时可能遇到内存问题。

**解决方案**: 分块处理数据或增加系统内存

#### 模型训练慢
**解决方案**: 
- 减少训练数据量
- 使用更简单的模型
- 使用 GPU 加速（如果可用）

## 进一步阅读

- [API 文档](API.md)
- [设置指南](../SETUP.md)
- [贡献指南](../CONTRIBUTING.md)

## 获取帮助

如果遇到问题：
1. 查看文档
2. 搜索已有的 Issues
3. 创建新的 Issue 描述问题
