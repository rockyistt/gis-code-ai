"""
辅助工具函数
"""
import logging
import os
from pathlib import Path


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 创建控制台处理器
    handler = logging.StreamHandler()
    handler.setLevel(level)
    
    # 设置格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    # 添加处理器
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger


def validate_file(file_path: str, extensions: list = None) -> bool:
    """
    验证文件是否存在且格式正确
    
    Args:
        file_path: 文件路径
        extensions: 允许的文件扩展名列表（如 ['.shp', '.geojson']）
    
    Returns:
        bool: 文件是否有效
    
    Raises:
        FileNotFoundError: 如果文件不存在
        ValueError: 如果文件格式不正确
    """
    path = Path(file_path)
    
    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 检查是否为文件
    if not path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")
    
    # 检查文件扩展名
    if extensions:
        if path.suffix.lower() not in [ext.lower() for ext in extensions]:
            raise ValueError(
                f"不支持的文件格式: {path.suffix}。"
                f"支持的格式: {', '.join(extensions)}"
            )
    
    return True


def create_directory(dir_path: str) -> Path:
    """
    创建目录（如果不存在）
    
    Args:
        dir_path: 目录路径
    
    Returns:
        Path对象
    """
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)
    return path
