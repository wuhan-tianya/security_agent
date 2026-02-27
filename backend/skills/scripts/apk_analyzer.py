"""
APK 分析工具模块

本模块提供 APK 文件的基本信息分析功能，包括：
- 应用基本信息（包名、版本、SDK 版本等）
- Android 组件（Activity、Service、Receiver、Provider）
- 权限列表
- 证书信息

依赖:
    androguard: Android 应用分析库
        安装: pip install androguard
"""
import os
from typing import Dict, Any, List
from .base_tool import BaseTool

# 尝试导入 androguard，如果未安装则设置为 None
try:
    from androguard.core.apk import APK
    from androguard.core.axml import AXML
except ImportError:
    APK = None
    AXML = None


class APKAnalyzer(BaseTool):
    """
    APK 文件分析工具
    
    用于分析 Android APK 文件的基本信息，包括应用元数据、
    Android 组件、权限和证书信息。
    
    此类继承自 BaseTool，实现了 execute 方法来执行 APK 分析。
    
    Attributes:
        name (str): 工具名称 "apk_analyzer"
        description (str): 工具描述
    
    Example:
        >>> analyzer = APKAnalyzer()
        >>> result = analyzer.execute(apk_path="/path/to/app.apk")
        >>> if result["success"]:
        ...     print(f"包名: {result['data']['package_name']}")
    """
    
    def __init__(self):
        """
        初始化 APK 分析工具
        
        设置工具的名称和描述信息。
        """
        super().__init__(
            name="apk_analyzer",
            description="分析 APK 文件的基本信息、组件、证书等"
        )
    
    def execute(self, apk_path: str, **kwargs) -> Dict[str, Any]:
        """
        执行 APK 文件分析
        
        分析指定的 APK 文件，提取应用的基本信息、组件列表、
        权限列表和证书信息。
        
        Args:
            apk_path: APK 文件的完整路径
            **kwargs: 其他可选参数（当前未使用）
        
        Returns:
            Dict[str, Any]: 分析结果字典，包含以下结构：
                - success (bool): 分析是否成功
                - data (dict): 分析数据（成功时），包含：
                    - package_name (str): 应用包名
                    - app_name (str): 应用名称
                    - version_name (str): 版本名称
                    - version_code (str): 版本代码
                    - min_sdk_version (str): 最低 SDK 版本
                    - target_sdk_version (str): 目标 SDK 版本
                    - activities (list): Activity 组件列表
                    - services (list): Service 组件列表
                    - receivers (list): BroadcastReceiver 组件列表
                    - providers (list): ContentProvider 组件列表
                    - permissions (list): 权限列表
                    - certificates (list): 证书信息列表
                    - file_size (int): APK 文件大小（字节）
                - error (str): 错误信息（失败时）
        
        Raises:
            不抛出异常，所有错误都通过返回字典中的 error 字段表示
        
        Example:
            >>> analyzer = APKAnalyzer()
            >>> result = analyzer.execute(apk_path="/path/to/app.apk")
            >>> if result["success"]:
            ...     data = result["data"]
            ...     print(f"包名: {data['package_name']}")
            ...     print(f"权限数: {len(data['permissions'])}")
        """
        # 检查文件是否存在
        if not os.path.exists(apk_path):
            return {
                "success": False,
                "error": f"APK 文件不存在: {apk_path}",
                "data": {}
            }
        
        # 检查 androguard 是否已安装
        if APK is None:
            return {
                "success": False,
                "error": "androguard 未安装，请安装: pip install androguard",
                "data": {}
            }
        
        try:
            # 使用 androguard 加载 APK 文件
            apk = APK(apk_path)
            
            # 构建分析结果
            result = {
                "success": True,
                "data": {
                    # 应用基本信息
                    "package_name": apk.get_package(),  # 应用包名
                    "app_name": apk.get_app_name(),  # 应用显示名称
                    "version_name": apk.get_androidversion_name(),  # 版本名称（如 "1.0.0"）
                    "version_code": apk.get_androidversion_code(),  # 版本代码（整数）
                    # SDK 版本信息
                    "min_sdk_version": apk.get_min_sdk_version(),  # 最低支持的 Android SDK 版本
                    "target_sdk_version": apk.get_target_sdk_version(),  # 目标 Android SDK 版本
                    # Android 组件列表
                    "activities": list(apk.get_activities()),  # Activity 组件列表
                    "services": list(apk.get_services()),  # Service 组件列表
                    "receivers": list(apk.get_receivers()),  # BroadcastReceiver 组件列表
                    "providers": list(apk.get_providers()),  # ContentProvider 组件列表
                    # 权限和证书
                    "permissions": list(apk.get_permissions()),  # 申请的权限列表
                    "certificates": self._analyze_certificates(apk),  # 签名证书信息
                    # 文件信息
                    "file_size": os.path.getsize(apk_path),  # APK 文件大小（字节）
                }
            }
            
            return result
            
        except Exception as e:
            # 捕获所有异常，返回错误信息
            return {
                "success": False,
                "error": f"分析 APK 时出错: {str(e)}",
                "data": {}
            }
    
    def _analyze_certificates(self, apk) -> List[Dict[str, Any]]:
        """
        分析 APK 文件的签名证书信息
        
        提取 APK 文件中包含的所有签名证书的详细信息，
        包括颁发者、主题和序列号。
        
        Args:
            apk: androguard APK 对象实例
        
        Returns:
            List[Dict[str, Any]]: 证书信息列表，每个证书包含：
                - issuer (str): 证书颁发者
                - subject (str): 证书主题
                - serial_number (str): 证书序列号
                如果分析失败，列表可能包含 {"error": "错误信息"}
        
        Note:
            如果证书分析过程中出现异常，会在结果中添加错误信息，
            而不是抛出异常。
        """
        certs = []
        try:
            # 遍历所有证书
            for cert in apk.get_certificates():
                cert_info = {
                    "issuer": str(cert.issuer),  # 证书颁发者信息
                    "subject": str(cert.subject),  # 证书主题信息
                    "serial_number": str(cert.serial_number),  # 证书序列号
                }
                certs.append(cert_info)
        except Exception as e:
            # 如果证书分析失败，记录错误
            certs.append({"error": str(e)})
        
        return certs

