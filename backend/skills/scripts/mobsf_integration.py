"""
MobSF 功能集成模块
将 MobSF 的核心功能封装为工具类
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加 MobSF 路径以便导入
mobsf_path = Path(__file__).parent.parent / "security-lib"
if mobsf_path.exists():
    sys.path.insert(0, str(mobsf_path))

logger = logging.getLogger(__name__)

try:
    from androguard.core.apk import APK
    from androguard.core.axml import AXML
    ANDROGUARD_AVAILABLE = True
except ImportError:
    ANDROGUARD_AVAILABLE = False
    APK = None
    AXML = None


class MobSFIntegration:
    """MobSF 功能集成类"""
    
    def __init__(self):
        self.resources_dir = Path(__file__).parent.parent / "resources"
        self.mobsf_path = Path(__file__).parent.parent / "security-lib"
    
    def get_apktool_path(self) -> Optional[Path]:
        """获取 apktool 路径"""
        apktool = self.resources_dir / "apktool_2.10.0.jar"
        if apktool.exists():
            return apktool
        return None
    
    def get_baksmali_path(self) -> Optional[Path]:
        """获取 baksmali 路径"""
        baksmali = self.resources_dir / "baksmali-3.0.8-dev-fat.jar"
        if baksmali.exists():
            return baksmali
        return None
    
    def get_apksigner_path(self) -> Optional[Path]:
        """获取 apksigner 路径"""
        apksigner = self.resources_dir / "apksigner.jar"
        if apksigner.exists():
            return apksigner
        return None
    
    def analyze_apk_static(self, apk_path: str) -> Dict[str, Any]:
        """
        执行 MobSF 风格的静态分析
        
        Args:
            apk_path: APK 文件路径
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not ANDROGUARD_AVAILABLE:
            return {
                "success": False,
                "error": "androguard 未安装",
                "data": {}
            }
        
        try:
            apk = APK(apk_path)
            
            # 基本信息
            basic_info = {
                "package_name": apk.get_package(),
                "app_name": apk.get_app_name(),
                "version_name": apk.get_androidversion_name(),
                "version_code": apk.get_androidversion_code(),
                "min_sdk_version": apk.get_min_sdk_version(),
                "target_sdk_version": apk.get_target_sdk_version(),
            }
            
            # 权限分析
            permissions = list(apk.get_permissions())
            
            # 组件分析
            components = {
                "activities": list(apk.get_activities()),
                "services": list(apk.get_services()),
                "receivers": list(apk.get_receivers()),
                "providers": list(apk.get_providers()),
            }
            
            # 证书分析
            certs = []
            try:
                for cert in apk.get_certificates():
                    certs.append({
                        "issuer": str(cert.issuer),
                        "subject": str(cert.subject),
                        "serial_number": str(cert.serial_number),
                    })
            except Exception:
                pass
            
            # 字符串提取
            strings = []
            try:
                d = apk.get_dex()
                if d:
                    strings = list(d.get_strings())[:1000]  # 限制数量
            except Exception:
                pass
            
            return {
                "success": True,
                "data": {
                    "basic_info": basic_info,
                    "permissions": permissions,
                    "components": components,
                    "certificates": certs,
                    "strings_sample": strings[:100],  # 只返回前100个字符串
                }
            }
        except Exception as e:
            logger.error(f"静态分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }

