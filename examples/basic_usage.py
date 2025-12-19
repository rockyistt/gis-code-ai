"""
基本使用示例

演示如何使用 GIS Code AI 进行基本操作
"""
from src.core.gis_processor import GISProcessor
from src.ai.model import AIModel
from src.utils.helpers import setup_logger


def main():
    """主函数"""
    # 设置日志
    logger = setup_logger("example")
    logger.info("欢迎使用 GIS Code AI!")
    
    # 创建 GIS 处理器
    logger.info("创建 GIS 处理器...")
    processor = GISProcessor()
    
    # 创建 AI 模型
    logger.info("创建 AI 模型...")
    model = AIModel(model_type="classification")
    
    # 示例：处理GIS数据
    logger.info("处理 GIS 数据...")
    # processor.load_data("path/to/your/data.shp")
    # processor.process()
    
    # 示例：使用AI模型
    logger.info("训练 AI 模型...")
    # model.train(X_train, y_train)
    # predictions = model.predict(X_test)
    
    logger.info("示例执行完成!")
    print("\n✅ 基本示例运行成功！")
    print("📖 查看 SETUP.md 了解更多详细信息")


if __name__ == "__main__":
    main()
