"""
动态扫描工具
基于 MobSF 的动态分析功能
使用 Frida 进行运行时分析
"""
import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

try:
    import frida
    FRIDA_AVAILABLE = True
except ImportError:
    FRIDA_AVAILABLE = False
    frida = None


class DynamicScanner(BaseTool):
    """动态扫描工具（基于 MobSF，使用 Frida）"""
    
    def __init__(self):
        super().__init__(
            name="dynamic_scanner",
            description="APK 动态安全分析，包括运行时行为监控、API 调用跟踪、网络流量分析等"
        )
        self.resources_dir = Path(__file__).parent.parent / "resources"
        self.frida_scripts_dir = self.resources_dir / "frida_scripts" / "android"
        self.frida_scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def execute(self, apk_path: str = None, package_name: str = None, 
                device_id: str = None, duration: int = 30, **kwargs) -> Dict[str, Any]:
        """
        执行动态扫描
        
        Args:
            apk_path: APK 文件路径（可选，用于获取包名）
            package_name: 应用包名（必需）
            device_id: 设备 ID（可选，默认使用第一个设备）
            duration: 监控持续时间（秒，默认30秒）
            
        Returns:
            Dict[str, Any]: 扫描结果
        """
        if not FRIDA_AVAILABLE:
            return {
                "success": False,
                "error": "Frida 未安装，请安装: pip install frida frida-tools",
                "data": {}
            }
        
        # 获取包名
        if not package_name and apk_path:
            package_name = self._get_package_name(apk_path)
        
        if not package_name:
            return {
                "success": False,
                "error": "需要提供 package_name 或 apk_path",
                "data": {}
            }
        
        try:
            # 连接设备
            device = self._get_device(device_id)
            if not device:
                return {
                    "success": False,
                    "error": "无法连接到设备，请确保设备已连接且已启用 USB 调试",
                    "data": {}
                }
            
            # 检查应用是否已安装
            if not self._is_app_installed(device, package_name):
                return {
                    "success": False,
                    "error": f"应用 {package_name} 未安装，请先安装应用",
                    "data": {}
                }
            
            # 执行动态分析
            results = {
                "success": True,
                "data": {
                    "package_name": package_name,
                    "device_id": device.id if device else None,
                    "monitoring_duration": duration,
                    "api_calls": [],
                    "permission_usage": [],
                    "network_activity": [],
                    "file_operations": [],
                    "security_events": [],
                    "summary": {}
                }
            }
            
            # 启动应用并监控
            self._start_app(device, package_name)
            time.sleep(2)  # 等待应用启动
            
            # 附加到进程并监控
            session = device.attach(package_name)
            
            # 加载监控脚本
            script = session.create_script(self._get_monitoring_script())
            # 创建消息处理器（避免闭包问题）
            def message_handler(message, data):
                self._on_message(message, data, results)
            script.on('message', message_handler)
            script.load()
            
            # 监控指定时间
            time.sleep(duration)
            
            # 停止监控
            session.detach()
            
            # 生成摘要
            results["data"]["summary"] = self._generate_summary(results["data"])
            
            return results
            
        except Exception as e:
            return {
                "success": False,
                "error": f"动态扫描时出错: {str(e)}",
                "data": {}
            }
    
    def _get_device(self, device_id: Optional[str] = None):
        """获取设备"""
        try:
            if device_id:
                return frida.get_device(device_id)
            else:
                # 获取第一个 USB 设备
                devices = frida.enumerate_devices()
                for device in devices:
                    if device.type == 'usb':
                        return device
                # 如果没有 USB 设备，尝试本地设备
                return frida.get_usb_device()
        except Exception:
            return None
    
    def _is_app_installed(self, device, package_name: str) -> bool:
        """检查应用是否已安装"""
        try:
            applications = device.enumerate_applications()
            for app in applications:
                if app.identifier == package_name:
                    return True
            return False
        except Exception:
            return False
    
    def _start_app(self, device, package_name: str):
        """启动应用"""
        try:
            # 使用 adb 启动应用
            subprocess.run(
                ["adb", "shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
    
    def _get_package_name(self, apk_path: str) -> Optional[str]:
        """从 APK 获取包名"""
        try:
            from androguard.core.apk import APK
            apk = APK(apk_path)
            return apk.get_package()
        except Exception:
            return None
    
    def _get_monitoring_script(self, script_type: str = "default") -> str:
        """
        获取监控脚本（基于 MobSF 的 Frida 脚本）
        
        Args:
            script_type: 脚本类型（default, auxiliary, others）
        """
        scripts = []
        
        # 加载 MobSF 的默认脚本
        default_dir = self.frida_scripts_dir / "default"
        if default_dir.exists():
            # 加载 API 监控脚本
            api_monitor = default_dir / "api_monitor.js"
            if api_monitor.exists():
                scripts.append(api_monitor.read_text('utf-8', 'ignore'))
            
            # 加载 SSL Pinning 绕过脚本
            ssl_bypass = default_dir / "ssl_pinning_bypass.js"
            if ssl_bypass.exists():
                scripts.append(ssl_bypass.read_text('utf-8', 'ignore'))
            
            # 加载剪贴板转储脚本
            clipboard = default_dir / "dump_clipboard.js"
            if clipboard.exists():
                scripts.append(clipboard.read_text('utf-8', 'ignore'))
        
        # 加载辅助脚本
        auxiliary_dir = self.frida_scripts_dir / "auxiliary"
        if auxiliary_dir.exists():
            # 加载字符串捕获脚本
            string_catch = auxiliary_dir / "string_catch.js"
            if string_catch.exists():
                scripts.append(string_catch.read_text('utf-8', 'ignore'))
        
        # 如果找不到 MobSF 脚本，使用基础脚本
        if not scripts:
            return self._get_basic_monitoring_script()
        
        # 组合所有脚本
        return '\n'.join(scripts)
    
    def _get_basic_monitoring_script(self) -> str:
        """获取基础监控脚本（备用）"""
        return """
        Java.perform(function() {
            console.log("[*] 开始动态监控");
            
            // 监控权限检查
            var PackageManager = Java.use("android.content.pm.PackageManager");
            PackageManager.checkPermission.implementation = function(perm, pkg) {
                var result = this.checkPermission(perm, pkg);
                send({
                    type: "permission_check",
                    permission: perm,
                    package: pkg,
                    granted: result == 0
                });
                return result;
            };
            
            // 监控网络请求
            try {
                var HttpURLConnection = Java.use("java.net.HttpURLConnection");
                HttpURLConnection.connect.implementation = function() {
                    var url = this.getURL().toString();
                    send({
                        type: "network_request",
                        url: url,
                        method: this.getRequestMethod()
                    });
                    return this.connect();
                };
            } catch(e) {
                console.log("[!] 无法监控 HttpURLConnection: " + e);
            }
            
            console.log("[*] 监控脚本已加载");
        });
        """
    
    def _on_message(self, message: Dict, data: Any, results: Dict[str, Any]):
        """处理 Frida 消息"""
        try:
            if message['type'] == 'send':
                payload = message['payload']
                event_type = payload.get('type')
                
                if event_type == 'permission_check':
                    results["data"]["permission_usage"].append({
                        "permission": payload.get("permission"),
                        "package": payload.get("package"),
                        "granted": payload.get("granted"),
                        "timestamp": time.time()
                    })
                
                elif event_type == 'network_request':
                    results["data"]["network_activity"].append({
                        "url": payload.get("url"),
                        "method": payload.get("method"),
                        "timestamp": time.time()
                    })
                
                elif event_type == 'file_operation':
                    results["data"]["file_operations"].append({
                        "path": payload.get("path"),
                        "operation": payload.get("operation"),
                        "timestamp": time.time()
                    })
                
                elif event_type == 'security_event':
                    results["data"]["security_events"].append({
                        "event": payload.get("event"),
                        "details": payload,
                        "timestamp": time.time()
                    })
        except Exception as e:
            pass
    
    def _generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """生成摘要"""
        summary = {
            "total_events": 0,
            "permission_checks": len(data.get("permission_usage", [])),
            "network_requests": len(data.get("network_activity", [])),
            "file_operations": len(data.get("file_operations", [])),
            "security_events": len(data.get("security_events", [])),
            "risks": []
        }
        
        summary["total_events"] = (
            summary["permission_checks"] +
            summary["network_requests"] +
            summary["file_operations"] +
            summary["security_events"]
        )
        
        # 检查安全风险
        if data.get("security_events"):
            summary["risks"].append({
                "type": "敏感数据存储",
                "count": len(data["security_events"]),
                "severity": "高"
            })
        
        # 检查不安全的网络请求
        insecure_requests = [
            req for req in data.get("network_activity", [])
            if req.get("url", "").startswith("http://")
        ]
        if insecure_requests:
            summary["risks"].append({
                "type": "不安全的网络请求",
                "count": len(insecure_requests),
                "severity": "中"
            })
        
        return summary

