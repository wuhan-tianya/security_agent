"""
MobSF 静态分析工具
基于 MobSF 的完整静态分析功能
"""
import os
import sys
import logging
import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

# 添加 MobSF 路径
mobsf_path = Path(__file__).parent.parent / "security-lib"
if mobsf_path.exists():
    sys.path.insert(0, str(mobsf_path))

logger = logging.getLogger(__name__)

try:
    from androguard.core.apk import APK
    from androguard.core.bytecodes import dvm
    ANDROGUARD_AVAILABLE = True
except ImportError:
    ANDROGUARD_AVAILABLE = False
    APK = None
    dvm = None


class MobSFStaticAnalyzer(BaseTool):
    """
    MobSF 静态分析工具
    基于 MobSF 的完整静态分析功能
    """
    
    def __init__(self):
        super().__init__(
            name="mobsf_static_analyzer",
            description="基于 MobSF 的完整静态安全分析，包括 APK 分析、Manifest 分析、代码分析、证书分析、字符串提取等"
        )
        self.resources_dir = Path(__file__).parent.parent / "resources"
        self.mobsf_path = mobsf_path
    
    def execute(self, apk_path: str, **kwargs) -> Dict[str, Any]:
        """
        执行 MobSF 风格的静态分析
        
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
        
        if not ANDROGUARD_AVAILABLE:
            return {
                "success": False,
                "error": "androguard 未安装，请安装: pip install androguard",
                "data": {}
            }
        
        try:
            # 计算文件哈希
            file_hash = self._calculate_hash(apk_path)
            
            # 使用 androguard 解析 APK
            apk = APK(apk_path)
            
            # 执行各项分析
            results = {
                "success": True,
                "data": {
                    # 基本信息（基于 MobSF 的 apk.py）
                    "basic_info": self._get_basic_info(apk, apk_path, file_hash),
                    # Manifest 分析（基于 MobSF 的 manifest_analysis.py）
                    "manifest_analysis": self._analyze_manifest(apk),
                    # 权限分析
                    "permissions": self._analyze_permissions(apk),
                    # 组件分析
                    "components": self._analyze_components(apk),
                    # 证书分析（基于 MobSF 的 cert_analysis.py）
                    "certificates": self._analyze_certificates_mobsf(apk),
                    # 字符串分析（基于 MobSF 的 strings.py）
                    "strings": self._analyze_strings_mobsf(apk),
                    # 代码分析（基于 MobSF 的 code_analysis.py）
                    "code_analysis": self._analyze_code_mobsf(apk),
                    # 网络安全配置
                    "network_security": self._analyze_network_security(apk),
                    # 硬编码证书/密钥库检查
                    "hardcoded_secrets": self._check_hardcoded_secrets(apk),
                }
            }
            
            # 生成安全摘要
            results["data"]["security_summary"] = self._generate_security_summary(results["data"])
            
            return results
            
        except Exception as e:
            logger.error(f"MobSF 静态分析失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"静态分析时出错: {str(e)}",
                "data": {}
            }
    
    def _calculate_hash(self, file_path: str) -> Dict[str, str]:
        """计算文件哈希（基于 MobSF 的 hash_gen）"""
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        
        block_size = 65536
        with open(file_path, 'rb') as f:
            while True:
                buf = f.read(block_size)
                if not buf:
                    break
                md5.update(buf)
                sha1.update(buf)
                sha256.update(buf)
        
        return {
            "md5": md5.hexdigest(),
            "sha1": sha1.hexdigest(),
            "sha256": sha256.hexdigest()
        }
    
    def _get_basic_info(self, apk: APK, apk_path: str, file_hash: Dict[str, str]) -> Dict[str, Any]:
        """获取基本信息（基于 MobSF 的 app.py）"""
        file_size = os.path.getsize(apk_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)
        
        return {
            "package_name": apk.get_package(),
            "app_name": apk.get_app_name(),
            "version_name": apk.get_androidversion_name(),
            "version_code": apk.get_androidversion_code(),
            "min_sdk_version": apk.get_min_sdk_version(),
            "target_sdk_version": apk.get_target_sdk_version(),
            "file_size": file_size,
            "file_size_mb": f"{file_size_mb}MB",
            "md5": file_hash["md5"],
            "sha1": file_hash["sha1"],
            "sha256": file_hash["sha256"],
        }
    
    def _analyze_manifest(self, apk: APK) -> Dict[str, Any]:
        """分析 Manifest（基于 MobSF 的 manifest_analysis.py）"""
        findings = []
        security_issues = []
        
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return {"findings": [], "security_issues": []}
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            application = manifest.find('.//application')
            
            if application is not None:
                # 检查调试模式
                debuggable = application.get(f'{{{ns["android"]}}}debuggable', 'false')
                if debuggable == 'true':
                    findings.append({
                        "type": "调试模式",
                        "severity": "高",
                        "description": "应用启用了调试模式，生产环境应禁用"
                    })
                    security_issues.append("应用可调试")
                
                # 检查备份允许
                allow_backup = application.get(f'{{{ns["android"]}}}allowBackup', 'true')
                if allow_backup == 'true':
                    findings.append({
                        "type": "备份允许",
                        "severity": "中",
                        "description": "应用允许备份，可能导致数据泄露"
                    })
                    security_issues.append("允许备份")
                
                # 检查网络安全配置
                network_security_config = application.get(
                    f'{{{ns["android"]}}}networkSecurityConfig', None
                )
                if network_security_config is None:
                    findings.append({
                        "type": "网络安全配置",
                        "severity": "中",
                        "description": "未配置网络安全策略，可能允许不安全的网络连接"
                    })
                    security_issues.append("未配置网络安全策略")
        except Exception as e:
            logger.warning(f"Manifest 分析出错: {e}")
        
        return {
            "findings": findings,
            "security_issues": security_issues,
            "issue_count": len(security_issues)
        }
    
    def _analyze_permissions(self, apk: APK) -> Dict[str, Any]:
        """分析权限（基于 MobSF 的权限分析）"""
        permissions = list(apk.get_permissions())
        
        # 危险权限列表（基于 MobSF 的权限分类）
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
        
        try:
            manifest = apk.get_android_manifest_xml()
            if manifest is None:
                return {}
            
            ns = {'android': 'http://schemas.android.com/apk/res/android'}
            
            # 检查导出的 Activities
            for activity in apk.get_activities():
                if self._is_component_exported(manifest, activity, "activity", ns):
                    exported_activities.append(activity)
            
            # 检查导出的 Services
            for service in apk.get_services():
                if self._is_component_exported(manifest, service, "service", ns):
                    exported_services.append(service)
            
            # 检查导出的 Receivers
            for receiver in apk.get_receivers():
                if self._is_component_exported(manifest, receiver, "receiver", ns):
                    exported_receivers.append(receiver)
            
            # 检查导出的 Providers
            for provider in apk.get_providers():
                if self._is_component_exported(manifest, provider, "provider", ns):
                    exported_providers.append(provider)
        except Exception as e:
            logger.warning(f"组件分析出错: {e}")
        
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
    
    def _analyze_certificates_mobsf(self, apk: APK) -> Dict[str, Any]:
        """分析证书（基于 MobSF 的 cert_analysis.py）"""
        certs_info = []
        hardcoded_certs = []
        
        try:
            # 分析签名证书
            for cert in apk.get_certificates():
                cert_info = {
                    "issuer": str(cert.issuer),
                    "subject": str(cert.subject),
                    "serial_number": str(cert.serial_number),
                }
                certs_info.append(cert_info)
        except Exception as e:
            logger.warning(f"证书分析出错: {e}")
        
        # 检查硬编码证书（基于 MobSF 的 get_hardcoded_cert_keystore）
        try:
            files = apk.get_files()
            cert_extensions = ['.cer', '.pem', '.cert', '.crt', '.pub', '.key', '.pfx', '.p12', '.der']
            keystore_extensions = ['.jks', '.bks']
            
            for file_name in files:
                if '.' not in file_name:
                    continue
                ext = Path(file_name).suffix.lower()
                if ext in cert_extensions:
                    hardcoded_certs.append(file_name)
                elif ext in keystore_extensions:
                    hardcoded_certs.append(file_name)
        except Exception:
            pass
        
        return {
            "certificates": certs_info,
            "certificate_count": len(certs_info),
            "hardcoded_certificates": hardcoded_certs,
            "hardcoded_count": len(hardcoded_certs),
        }
    
    def _analyze_strings_mobsf(self, apk: APK) -> Dict[str, Any]:
        """分析字符串（基于 MobSF 的 strings.py）"""
        strings = []
        urls = []
        emails = []
        secrets = []
        
        try:
            d = apk.get_dex()
            if d:
                all_strings = list(d.get_strings())
                strings = all_strings[:1000]  # 限制数量
                
                # 提取 URL 和邮箱（基于 MobSF 的 url_n_email_extract）
                import re
                url_pattern = re.compile(
                    r'https?://[^\s<>"{}|\\^`\[\]]+',
                    re.IGNORECASE
                )
                email_pattern = re.compile(
                    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                )
                
                for s in all_strings[:5000]:  # 限制检查数量
                    # 提取 URL
                    url_matches = url_pattern.findall(s)
                    urls.extend(url_matches)
                    
                    # 提取邮箱
                    email_matches = email_pattern.findall(s)
                    emails.extend(email_matches)
                    
                    # 检查可能的密钥（基于 MobSF 的 is_secret_key）
                    if self._is_secret_key(s):
                        secrets.append(s[:100])  # 限制长度
        except Exception as e:
            logger.warning(f"字符串分析出错: {e}")
        
        return {
            "total_strings": len(strings),
            "strings_sample": strings[:100],  # 只返回前100个
            "urls": list(set(urls))[:50],  # 去重并限制数量
            "url_count": len(set(urls)),
            "emails": list(set(emails))[:20],  # 去重并限制数量
            "email_count": len(set(emails)),
            "potential_secrets": secrets[:20],  # 限制数量
            "secret_count": len(secrets),
        }
    
    def _analyze_code_mobsf(self, apk: APK) -> Dict[str, Any]:
        """分析代码（基于 MobSF 的 code_analysis.py）"""
        findings = []
        
        # 检查是否使用混淆
        is_obfuscated = self._check_obfuscation(apk)
        
        # 检查调试信息
        if self._is_debuggable(apk):
            findings.append({
                "type": "调试模式",
                "severity": "高",
                "description": "应用启用了调试模式"
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
    
    def _check_hardcoded_secrets(self, apk: APK) -> List[str]:
        """检查硬编码密钥（基于 MobSF 的 get_hardcoded_cert_keystore）"""
        secrets = []
        try:
            files = apk.get_files()
            secret_extensions = ['.cer', '.pem', '.cert', '.crt', '.pub', '.key', '.pfx', '.p12', '.der', '.jks', '.bks']
            for file_name in files:
                if any(file_name.lower().endswith(ext) for ext in secret_extensions):
                    secrets.append(file_name)
        except Exception:
            pass
        return secrets
    
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
        
        # 统计硬编码证书
        if data.get("certificates", {}).get("hardcoded_count", 0) > 0:
            summary["total_risks"] += 1
            summary["high_risks"] += 1
            summary["risk_items"].append({
                "type": "硬编码证书",
                "count": data["certificates"]["hardcoded_count"],
                "severity": "高"
            })
        
        return summary
    
    # 辅助方法
    def _is_component_exported(self, manifest, component_name: str, component_type: str, ns: dict) -> bool:
        """检查组件是否导出"""
        try:
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
    
    def _check_obfuscation(self, apk: APK) -> bool:
        """检查是否使用混淆"""
        try:
            d = apk.get_dex()
            if d:
                classes = d.get_classes()
                obfuscated_count = 0
                for class_name in list(classes)[:10]:
                    if len(class_name.split('.')[-1]) <= 2:
                        obfuscated_count += 1
                return obfuscated_count > 5
        except Exception:
            pass
        return False
    
    def _is_secret_key(self, s: str) -> bool:
        """检查是否是密钥（基于 MobSF 的 is_secret_key）"""
        import re
        secret_patterns = [
            r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?',
            r'(?i)(secret[_-]?key|secretkey)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?',
            r'(?i)(password|pwd)\s*[=:]\s*["\']?[A-Za-z0-9]{8,}["\']?',
            r'(?i)(token|access[_-]?token)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?',
        ]
        for pattern in secret_patterns:
            if re.search(pattern, s):
                return True
        return False

