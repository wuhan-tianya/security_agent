"""
基础工具类模块

本模块定义了所有安全测试工具的基础抽象类 BaseTool。
所有具体的安全测试工具都应该继承此类并实现 execute 方法。

示例:
    class MyTool(BaseTool):
        def __init__(self):
            super().__init__("my_tool", "我的工具描述")
        
        def execute(self, **kwargs):
            # 实现工具逻辑
            return {"success": True, "data": {}}
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import json


class BaseTool(ABC):
    """
    所有安全测试工具的基础抽象类
    
    此类定义了安全测试工具的标准接口，所有具体工具必须继承此类。
    工具应该实现 execute 方法来执行具体的测试逻辑。
    
    Attributes:
        name (str): 工具名称，用于标识工具
        description (str): 工具描述，说明工具的用途和功能
    
    Example:
        >>> tool = MyCustomTool()
        >>> result = tool.execute(param1="value1")
        >>> info = tool.get_info()
    """
    
    def __init__(self, name: str, description: str):
        """
        初始化基础工具
        
        Args:
            name: 工具名称，应该是唯一的标识符（如 "apk_analyzer"）
            description: 工具的功能描述，用于说明工具的用途
        """
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具的核心逻辑（抽象方法，必须由子类实现）
        
        此方法应该包含工具的主要执行逻辑，并返回标准化的结果格式。
        返回结果应包含 success 字段表示执行是否成功。
        
        Args:
            **kwargs: 可变关键字参数，不同工具可能需要不同的参数
                - apk_path: APK 文件路径（用于 APK 分析工具）
                - permissions: 权限列表（用于权限检查工具）
                - code_content: 代码内容（用于代码分析工具）
                - network_logs: 网络日志（用于网络分析工具）
        
        Returns:
            Dict[str, Any]: 标准化的测试结果字典，应包含以下字段：
                - success (bool): 执行是否成功
                - data (dict): 测试结果数据（成功时）
                - error (str): 错误信息（失败时）
        
        Raises:
            NotImplementedError: 如果子类未实现此方法
        
        Example:
            >>> result = tool.execute(apk_path="/path/to/app.apk")
            >>> if result["success"]:
            ...     print(result["data"])
        """
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取工具的基本信息
        
        返回工具的名称和描述，用于工具注册和查询。
        
        Returns:
            Dict[str, Any]: 包含工具信息的字典
                - name (str): 工具名称
                - description (str): 工具描述
        
        Example:
            >>> info = tool.get_info()
            >>> print(f"工具: {info['name']}, 描述: {info['description']}")
        """
        return {
            "name": self.name,
            "description": self.description
        }
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """
        将测试结果格式化为 JSON 字符串
        
        用于将结果字典转换为可读的 JSON 格式字符串，
        方便日志记录和结果展示。
        
        Args:
            result: 测试结果字典
        
        Returns:
            str: 格式化的 JSON 字符串，使用缩进和 UTF-8 编码
        
        Example:
            >>> result = {"success": True, "data": {"count": 5}}
            >>> formatted = tool.format_result(result)
            >>> print(formatted)
        """
        return json.dumps(result, indent=2, ensure_ascii=False)

