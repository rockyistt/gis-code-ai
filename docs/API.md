# API 文档

## 核心模块 (src.core)

### GISProcessor

GIS 数据处理器类。

#### 方法

##### `__init__()`
初始化 GIS 处理器。

##### `load_data(file_path: str)`
加载 GIS 数据文件。

**参数:**
- `file_path` (str): GIS 数据文件的路径

**返回:**
- 加载的数据对象

**异常:**
- `FileNotFoundError`: 如果文件不存在

##### `process()`
处理加载的 GIS 数据。

**返回:**
- 处理后的数据

##### `validate() -> bool`
验证 GIS 数据的有效性。

**返回:**
- `bool`: 数据是否有效

---

## AI 模块 (src.ai)

### AIModel

AI 模型基类，用于 GIS 数据的智能分析。

#### 方法

##### `__init__(model_type: str = "default")`
初始化 AI 模型。

**参数:**
- `model_type` (str): 模型类型，可选值包括 'classification', 'regression' 等

##### `train(X_train, y_train)`
训练模型。

**参数:**
- `X_train`: 训练特征数据
- `y_train`: 训练标签数据

##### `predict(X_test) -> Any`
使用训练好的模型进行预测。

**参数:**
- `X_test`: 测试数据

**返回:**
- 预测结果

**异常:**
- `RuntimeError`: 如果模型未训练

##### `evaluate(X_test, y_test) -> dict`
评估模型性能。

**参数:**
- `X_test`: 测试特征数据
- `y_test`: 测试标签数据

**返回:**
- 包含评估指标的字典

##### `save(file_path: str)`
保存模型到文件。

**参数:**
- `file_path` (str): 保存路径

##### `load(file_path: str)`
从文件加载模型。

**参数:**
- `file_path` (str): 模型文件路径

---

## 工具模块 (src.utils)

### helpers

#### 函数

##### `setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger`
设置并返回日志记录器。

**参数:**
- `name` (str): 日志记录器名称
- `level` (int): 日志级别

**返回:**
- `logging.Logger`: 配置好的日志记录器

##### `validate_file(file_path: str, extensions: list = None) -> bool`
验证文件是否存在且格式正确。

**参数:**
- `file_path` (str): 文件路径
- `extensions` (list): 允许的文件扩展名列表

**返回:**
- `bool`: 文件是否有效

**异常:**
- `FileNotFoundError`: 如果文件不存在
- `ValueError`: 如果文件格式不正确

##### `create_directory(dir_path: str) -> Path`
创建目录（如果不存在）。

**参数:**
- `dir_path` (str): 目录路径

**返回:**
- `Path`: Path 对象

---

## 使用示例

```python
from src.core.gis_processor import GISProcessor
from src.ai.model import AIModel
from src.utils.helpers import setup_logger

# 设置日志
logger = setup_logger("my_app")

# 使用 GIS 处理器
processor = GISProcessor()
processor.load_data("data.shp")
processor.process()

# 使用 AI 模型
model = AIModel(model_type="classification")
model.train(X_train, y_train)
predictions = model.predict(X_test)
```
