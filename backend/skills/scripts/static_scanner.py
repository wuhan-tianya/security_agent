"""
静态扫描工具
基于 MobSF 的静态分析功能
提供全面的 APK 静态安全分析
"""
import os
import json
import hashlib
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

try:
    from androguard.core.apk import APK
    from androguard.core.axml import AXML
    from androguard.core.bytecodes import dvm
except ImportError:
    APK = None
    AXML = None
    dvm = None


class StaticScanner(BaseTool):
    """静态扫描工具（基于 MobSF）"""
    
    def __init__(self):
        super().__init__(
            name="static_scanner",
            description="全面的 APK 静态安全分析，包括代码分析、权限分析、证书分析、字符串提取等"
        )
        self.resources_dir = Path(__file__).parent.parent / "resources"
    
    def execute(self, apk_path: str, **kwargs) -> Dict[str, Any]:
        """
        执行静态扫描
        
        Args:
            apk_path: APK 文件路径
            
        Returns:
            Dict[str, Any]: 扫描结果
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
            
            # 执行各项分析
            results = {
                "success": True,
                "data": {
                    # 基本信息
                    "basic_info": self._analyze_basic_info(apk, apk_path),
                    # 权限分析
                    "permissions": self._analyze_permissions(apk),
                    # 组件分析
                    "components": self._analyze_components(apk),
                    # 证书分析
                    "certificates": self._analyze_certificates(apk),
                    # 字符串分析
                    "strings": self._analyze_strings(apk),
                    # 代码分析
                    "code_analysis": self._analyze_code(apk),
                    # 网络安全配置
                    "network_security": self._analyze_network_security(apk),
                    # 安全风险汇总
                    "security_summary": {}
                }
            }
            
            # 生成安全风险汇总
            results["data"]["security_summary"] = self._generate_security_summary(results["data"])
            
            return results
            
        except Exception as e:
            return {
                "success": False,
                "error": f"静态扫描时出错: {str(e)}",
                "data": {}
            }
    
    def _analyze_basic_info(self, apk: APK, apk_path: str) -> Dict[str, Any]:
        """分析基本信息"""
        file_size = os.path.getsize(apk_path)
        md5_hash = self._calculate_md5(apk_path)
        
        return {
            "package_name": apk.get_package(),
            "app_name": apk.get_app_name(),
            "version_name": apk.get_androidversion_name(),
            "version_code": apk.get_androidversion_code(),
            "min_sdk_version": apk.get_min_sdk_version(),
            "target_sdk_version": apk.get_target_sdk_version(),
            "file_size": file_size,
            "md5": md5_hash,
            "is_debuggable": self._is_debuggable(apk),
            "allows_backup": self._allows_backup(apk),
        }
    
    def _analyze_permissions(self, apk: APK) -> Dict[str, Any]:
        """分析权限"""
        permissions = list(apk.get_permissions())
        
        # 危险权限列表
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
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
        ]
        
        dangerous_found = [p for p in permissions if p in dangerous_perms]
        
        return {
            "total_count": len(permissions),
            "permissions": permissions,
            "dangerous_permissions": dangerous_found,
            "dangerous_count": len(dangerous_found),
            "normal_permissions": [p for p in permissions if p not in dangerous_perms],
        }
    
    def _analyze_components(self, apk: APK) -> Dict[str, Any]:
        """分析组件"""
        exported_activities = []
        exported_services = []
        exported_receivers = []
        exported_providers = []
        
        # 检查导出的 Activities
        for activity in apk.get_activities():
            if self._is_component_exported(apk, activity, "activity"):
                exported_activities.append(activity)
        
        # 检查导出的 Services
        for service in apk.get_services():
            if self._is_component_exported(apk, service, "service"):
                exported_services.append(service)
        
        # 检查导出的 Receivers
        for receiver in apk.get_receivers():
            if self._is_component_exported(apk, receiver, "receiver"):
                exported_receivers.append(receiver)
        
        # 检查导出的 Providers
        for provider in apk.get_providers():
            if self._is_component_exported(apk, provider, "provider"):
                exported_providers.append(provider)
        
        return {
            "activities": {
                "total": len(apk.get_activities()),
                "exported": exported_activities,
                "exported_count": len(exported_activities),
            },
            "services": {
                "total": len(apk.get_services()),
                "exported": exported_services,
                "exported_count": len(exported_services),
            },
            "receivers": {
                "total": len(apk.get_receivers()),
                "exported": exported_receivers,
                "exported_count": len(exported_receivers),
            },
            "providers": {
                "total": len(apk.get_providers()),
                "exported": exported_providers,
                "exported_count": len(exported_providers),
            },
        }
    
    def _analyze_certificates(self, apk: APK) -> Dict[str, Any]:
        """分析证书"""
        certs_info = []
        
        try:
            for cert in apk.get_certificates():
                cert_info = {
                    "issuer": str(cert.issuer),
                    "subject": str(cert.subject),
                    "serial_number": str(cert.serial_number),
                }
                certs_info.append(cert_info)
        except Exception as e:
            pass
        
        # 检查硬编码证书
        hardcoded_certs = self._check_hardcoded_certificates(apk)
        
        return {
            "certificates": certs_info,
            "certificate_count": len(certs_info),
            "hardcoded_certificates": hardcoded_certs,
        }
    
    def _analyze_strings(self, apk: APK) -> Dict[str, Any]:
        """分析字符串"""
        strings = []
        urls = []
        emails = []
        potential_secrets = []
        
        try:
            # 提取字符串
            d = apk.get_dex()
            if d:
                for s in d.get_strings():
                    strings.append(s)
                    
                    # 提取 URL
                    if self._is_url(s):
                        urls.append(s)
                    
                    # 提取邮箱
                    if self._is_email(s):
                        emails.append(s)
                    
                    # 检查可能的密钥
                    if self._is_potential_secret(s):
                        potential_secrets.append(s)
        except Exception:
            pass
        
        return {
            "total_strings": len(strings),
            "urls": urls,
            "url_count": len(urls),
            "emails": emails,
            "email_count": len(emails),
            "potential_secrets": potential_secrets,
            "secret_count": len(potential_secrets),
        }
    
    def _analyze_code(self, apk: APK) -> Dict[str, Any]:
        """分析代码"""
        findings = []
        
        # 检查是否使用混淆
        is_obfuscated = self._check_obfuscation(apk)
        
        # 检查调试信息
        if self._is_debuggable(apk):
            findings.append({
                "type": "调试模式",
                "severity": "高",
                "description": "应用启用了调试模式",
            })
        
        # 检查备份允许
        if self._allows_backup(apk):
            findings.append({
                "type": "备份允许",
                "severity": "中",
                "description": "应用允许备份，可能导致数据泄露",
            })
        
        return {
            "is_obfuscated": is_obfuscated,
            "findings": findings,
            "findings_count": len(findings),
        }
    
    def _analyze_network_security(self, apk: APK) -> Dict[str, Any]:
        """分析网络安全配置"""
        issues = []
        
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                issues.append("未配置网络安全策略")
                return {"issues": issues}
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            if application is not None:
                network_security_config = application.get(
                    f'{{{ns["android"]}}}networkSecurityConfig', None
                )
                if network_security_config is None:
                    issues.append("未配置网络安全策略，可能允许不安全的网络连接")
        except Exception:
            pass
        
        return {"issues": issues, "issue_count": len(issues)}
    
    def _generate_security_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生成安全风险汇总"""
        summary = {
            "total_risks": 0,
            "high_risks": 0,
            "medium_risks": 0,
            "low_risks": 0,
            "risk_items": []
        }
        
        # 统计危险权限
        if data.get("permissions", {}).get("dangerous_count", 0) > 0:
            summary["total_risks"] += 1
            summary["high_risks"] += 1
            summary["risk_items"].append({
                "type": "危险权限",
                "count": data["permissions"]["dangerous_count"],
                "severity": "高"
            })
        
        # 统计导出组件
        components = data.get("components", {})
        total_exported = (
            components.get("activities", {}).get("exported_count", 0) +
            components.get("services", {}).get("exported_count", 0) +
            components.get("receivers", {}).get("exported_count", 0) +
            components.get("providers", {}).get("exported_count", 0)
        )
        if total_exported > 0:
            summary["total_risks"] += 1
            summary["medium_risks"] += 1
            summary["risk_items"].append({
                "type": "导出组件",
                "count": total_exported,
                "severity": "中"
            })
        
        # 统计潜在密钥
        if data.get("strings", {}).get("secret_count", 0) > 0:
            summary["total_risks"] += 1
            summary["high_risks"] += 1
            summary["risk_items"].append({
                "type": "潜在密钥",
                "count": data["strings"]["secret_count"],
                "severity": "高"
            })
        
        return summary
    
    # 辅助方法
    def _calculate_md5(self, file_path: str) -> str:
        """计算文件 MD5"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _is_debuggable(self, apk: APK) -> bool:
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
    
    def _allows_backup(self, apk: APK) -> bool:
        """检查是否允许备份"""
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return True
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            if application is not None:
                allow_backup = application.get(f'{{{ns["android"]}}}allowBackup', 'true')
                return allow_backup == 'true'
            return True
        except Exception:
            return True
    
    def _is_component_exported(self, apk: APK, component_name: str, component_type: str) -> bool:
        """检查组件是否导出"""
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return False
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            components = manifest.findall(f'.//{component_type}')
            for comp in components:
                name_attr = comp.get(f'{{{ns["android"]}}}name', '')
                if component_name in name_attr or name_attr in component_name:
                    exported = comp.get(f'{{{ns["android"]}}}exported', 'false')
                    if exported == 'true':
                        return True
                    if exported != 'false' and comp.findall('.//intent-filter'):
                        return True
            return False
        except Exception:
            return False
    
    def _check_hardcoded_certificates(self, apk: APK) -> List[str]:
        """检查硬编码证书"""
        cert_extensions = ['.cer', '.pem', '.cert', '.crt', '.pub', '.key', '.pfx', '.p12', '.der']
        found = []
        try:
            files = apk.get_files()
            for file_name in files:
                if any(file_name.endswith(ext) for ext in cert_extensions):
                    found.append(file_name)
        except Exception:
            pass
        return found
    
    def _is_url(self, s: str) -> bool:
        """检查是否是 URL"""
        return s.startswith(('http://', 'https://', 'ftp://'))
    
    def _is_email(self, s: str) -> bool:
        """检查是否是邮箱"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, s))
    
    def _is_potential_secret(self, s: str) -> bool:
        """检查是否是潜在的密钥"""
        import re
        # 检查常见的密钥模式
        patterns = [
            r'[A-Za-z0-9]{32,}',  # 长字符串
            r'(api[_-]?key|secret[_-]?key|password|token)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?',
        ]
        for pattern in patterns:
            if re.search(pattern, s, re.IGNORECASE):
                return True
        return False
    
    def _check_obfuscation(self, apk: APK) -> bool:
        """检查是否使用混淆"""
        # 简单的混淆检测：检查类名是否包含无意义的字符
        try:
            d = apk.get_dex()
            if d:
                classes = d.get_classes()
                # 如果类名大多是单字符或随机字符，可能是混淆
                obfuscated_count = 0
                for class_name in classes[:10]:  # 检查前10个类
                    if len(class_name.split('.')[-1]) <= 2:
                        obfuscated_count += 1
                return obfuscated_count > 5
        except Exception:
            pass
        return False

