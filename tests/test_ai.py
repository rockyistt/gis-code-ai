"""
AI模块测试
"""
import pytest
from src.ai.model import AIModel


class TestAIModel:
    """AI模型测试类"""
    
    def test_init(self):
        """测试模型初始化"""
        model = AIModel()
        assert model is not None
        assert model.model_type == "default"
        assert model.is_trained is False
    
    def test_init_with_type(self):
        """测试带类型参数的初始化"""
        model = AIModel(model_type="classification")
        assert model.model_type == "classification"
    
    def test_predict_without_training(self):
        """测试未训练时的预测行为"""
        model = AIModel()
        with pytest.raises(RuntimeError, match="模型尚未训练"):
            model.predict([1, 2, 3])
    
    def test_evaluate(self):
        """测试模型评估"""
        model = AIModel()
        result = model.evaluate(None, None)
        assert isinstance(result, dict)
        assert "accuracy" in result
