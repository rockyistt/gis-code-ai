"""
工具模块测试
"""
import pytest
import logging
import tempfile
from pathlib import Path
from src.utils.helpers import setup_logger, validate_file, create_directory


class TestHelpers:
    """工具函数测试类"""
    
    def test_setup_logger(self):
        """测试日志设置"""
        logger = setup_logger("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO
    
    def test_setup_logger_with_level(self):
        """测试带日志级别的日志设置"""
        logger = setup_logger("test_logger_debug", level=logging.DEBUG)
        assert logger.level == logging.DEBUG
    
    def test_validate_file_not_found(self):
        """测试不存在的文件"""
        with pytest.raises(FileNotFoundError):
            validate_file("nonexistent_file.txt")
    
    def test_validate_file_with_temp(self):
        """测试有效文件"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp_path = tmp.name
        
        try:
            result = validate_file(tmp_path)
            assert result is True
        finally:
            Path(tmp_path).unlink()
    
    def test_create_directory(self):
        """测试目录创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_subdir"
            result = create_directory(str(test_dir))
            assert result.exists()
            assert result.is_dir()
