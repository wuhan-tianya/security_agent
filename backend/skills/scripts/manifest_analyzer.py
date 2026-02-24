"""
Manifest 分析工具
基于 MobSF 的 Manifest 分析功能
分析 AndroidManifest.xml 的安全配置
"""
import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

try:
    from androguard.core.apk import APK
except ImportError:
    APK = None


class ManifestAnalyzer(BaseTool):
    """Manifest 分析工具"""
    
    def __init__(self):
        super().__init__(
            name="manifest_analyzer",
            description="分析 AndroidManifest.xml 的安全配置，包括组件导出、权限、网络安全配置等"
        )
    
    def execute(self, apk_path: str, **kwargs) -> Dict[str, Any]:
        """
        分析 Manifest
        
        Args:
            apk_path: APK 文件路径
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        if not os.path.exists(apk_path):
            return {
                "success": False,
                "error": f"APK 文件不存在: {apk_path}",
                "data": {}
            }
        
        if APK is None:
            return {
                "success": False,
                "error": "androguard 未安装，请安装: pip install androguard",
                "data": {}
            }
        
        try:
            apk = APK(apk_path)
            
            # 分析结果
            findings = []
            security_issues = []
            
            # 1. 检查导出的组件
            exported_components = self._check_exported_components(apk)
            if exported_components:
                findings.append({
                    "type": "导出组件检查",
                    "description": "发现导出的组件，可能存在安全风险",
                    "components": exported_components
                })
                security_issues.extend(exported_components)
            
            # 2. 检查调试模式
            if self._is_debuggable(apk):
                findings.append({
                    "type": "调试模式",
                    "description": "应用启用了调试模式，生产环境应禁用",
                    "severity": "高"
                })
                security_issues.append("应用可调试")
            
            # 3. 检查备份允许
            if self._is_backup_allowed(apk):
                findings.append({
                    "type": "备份允许",
                    "description": "应用允许备份，可能导致数据泄露",
                    "severity": "中"
                })
                security_issues.append("允许备份")
            
            # 4. 检查网络安全配置
            network_security = self._check_network_security(apk)
            if network_security.get("issues"):
                findings.append({
                    "type": "网络安全配置",
                    "description": "发现网络安全配置问题",
                    "issues": network_security["issues"]
                })
                security_issues.extend(network_security["issues"])
            
            # 5. 检查权限使用
            permission_analysis = self._analyze_permissions(apk)
            
            result = {
                "success": True,
                "data": {
                    "package_name": apk.get_package(),
                    "min_sdk": apk.get_min_sdk_version(),
                    "target_sdk": apk.get_target_sdk_version(),
                    "findings": findings,
                    "security_issues": security_issues,
                    "security_issue_count": len(security_issues),
                    "permission_analysis": permission_analysis,
                    "exported_activities": exported_components.get("activities", []),
                    "exported_services": exported_components.get("services", []),
                    "exported_receivers": exported_components.get("receivers", []),
                    "exported_providers": exported_components.get("providers", []),
                    "is_debuggable": self._is_debuggable(apk),
                    "allows_backup": self._is_backup_allowed(apk),
                }
            }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"分析 Manifest 时出错: {str(e)}",
                "data": {}
            }
    
    def _check_exported_components(self, apk) -> Dict[str, List[str]]:
        """检查导出的组件"""
        exported = {
            "activities": [],
            "services": [],
            "receivers": [],
            "providers": []
        }
        
        try:
            # 检查导出的 Activities
            for activity in apk.get_activities():
                if self._is_component_exported(apk, activity, "activity"):
                    exported["activities"].append(activity)
            
            # 检查导出的 Services
            for service in apk.get_services():
                if self._is_component_exported(apk, service, "service"):
                    exported["services"].append(service)
            
            # 检查导出的 Receivers
            for receiver in apk.get_receivers():
                if self._is_component_exported(apk, receiver, "receiver"):
                    exported["receivers"].append(receiver)
            
            # 检查导出的 Providers
            for provider in apk.get_providers():
                if self._is_component_exported(apk, provider, "provider"):
                    exported["providers"].append(provider)
        
        except Exception as e:
            pass
        
        return exported
    
    def _is_component_exported(self, apk, component_name: str, component_type: str) -> bool:
        """检查组件是否导出"""
        try:
            # 尝试从 AndroidManifest.xml 获取导出状态
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return False
            
            # 查找组件
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            components = manifest.findall(f'.//{component_type}')
            
            for comp in components:
                name_attr = comp.get(f'{{{ns["android"]}}}name', '')
                if component_name in name_attr or name_attr in component_name:
                    exported = comp.get(f'{{{ns["android"]}}}exported', 'false')
                    # 如果显式设置为 true，则导出
                    if exported == 'true':
                        return True
                    # 如果有 intent-filter 且没有显式设置为 false，则导出
                    if exported != 'false' and comp.findall('.//intent-filter'):
                        return True
            
            return False
        except Exception:
            return False
    
    def _is_debuggable(self, apk) -> bool:
        """检查是否可调试"""
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return False
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            if application is not None:
                debuggable = application.get(f'{{{ns["android"]}}}debuggable', 'false')
                return debuggable == 'true'
            return False
        except Exception:
            return False
    
    def _is_backup_allowed(self, apk) -> bool:
        """检查是否允许备份"""
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return True  # 默认允许备份
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            if application is not None:
                allow_backup = application.get(f'{{{ns["android"]}}}allowBackup', 'true')
                return allow_backup == 'true'
            return True
        except Exception:
            return True
    
    def _check_network_security(self, apk) -> Dict[str, Any]:
        """检查网络安全配置"""
        issues = []
        
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return {"issues": issues}
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            if application is not None:
                # 检查是否有网络安全配置
                network_security_config = application.get(
                    f'{{{ns["android"]}}}networkSecurityConfig', None
                )
                if network_security_config is None:
                    issues.append("未配置网络安全策略，可能允许不安全的网络连接")
        except Exception:
            pass
        
        return {"issues": issues}
    
    def _analyze_permissions(self, apk) -> Dict[str, Any]:
        """分析权限使用"""
        permissions = apk.get_permissions()
        
        # 危险权限分类
        dangerous_perms = [
            "android.permission.READ_SMS",
            "android.permission.SEND_SMS",
            "android.permission.RECEIVE_SMS",
            "android.permission.READ_PHONE_STATE",
            "android.permission.CALL_PHONE",
            "android.permission.READ_CONTACTS",
            "android.permission.WRITE_CONTACTS",
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.CAMERA",
            "android.permission.RECORD_AUDIO",
        ]
        
        dangerous_found = [p for p in permissions if p in dangerous_perms]
        
        return {
            "total_permissions": len(permissions),
            "dangerous_permissions": dangerous_found,
            "dangerous_count": len(dangerous_found)
        }

