"""
网络通信分析工具
分析应用的网络请求，检测不安全的通信
"""
import re
from typing import Dict, Any, List
from .base_tool import BaseTool


class NetworkAnalyzer(BaseTool):
    """网络通信分析工具"""
    
    def __init__(self):
        super().__init__(
            name="network_analyzer",
            description="分析应用的网络请求，检测不安全的通信（HTTP、证书验证等）"
        )
    
    def execute(self, code_content: str = None, network_logs: List[str] = None, **kwargs) -> Dict[str, Any]:
        """
        分析网络通信
        
        Args:
            code_content: 代码内容（可选）
            network_logs: 网络日志（可选）
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        issues = []
        
        if code_content:
            issues.extend(self._check_http_usage(code_content))
            issues.extend(self._check_certificate_pinning(code_content))
            issues.extend(self._check_hostname_verifier(code_content))
        
        if network_logs:
            issues.extend(self._analyze_network_logs(network_logs))
        
        result = {
            "success": True,
            "data": {
                "issues": issues,
                "total_count": len(issues),
                "risk_level": self._calculate_risk_level(issues)
            }
        }
        
        return result
    
    def _check_http_usage(self, content: str) -> List[Dict[str, Any]]:
        """检查是否使用 HTTP"""
        issues = []
        
        # 检查 HTTP URL
        http_pattern = r'http://[^\s"\'<>]+'
        matches = re.finditer(http_pattern, content)
        
        for match in matches:
            issues.append({
                "type": "不安全通信",
                "severity": "高",
                "description": f"使用 HTTP 协议，数据可能被窃听: {match.group(0)}",
                "recommendation": "建议使用 HTTPS"
            })
        
        return issues
    
    def _check_certificate_pinning(self, content: str) -> List[Dict[str, Any]]:
        """检查证书固定"""
        issues = []
        
        # 检查是否禁用证书验证
        dangerous_patterns = [
            r'\.setHostnameVerifier\s*\(.*ALLOW_ALL',
            r'TrustManager.*acceptAll',
            r'X509TrustManager',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                issues.append({
                    "type": "证书验证绕过",
                    "severity": "高",
                    "description": "发现禁用或绕过证书验证的代码",
                    "recommendation": "建议实现证书固定（Certificate Pinning）"
                })
                break
        
        return issues
    
    def _check_hostname_verifier(self, content: str) -> List[Dict[str, Any]]:
        """检查主机名验证"""
        issues = []
        
        if re.search(r'HostnameVerifier.*return\s+true', content, re.IGNORECASE):
            issues.append({
                "type": "主机名验证绕过",
                "severity": "高",
                "description": "发现总是返回 true 的主机名验证器",
                "recommendation": "实现正确的主机名验证"
            })
        
        return issues
    
    def _analyze_network_logs(self, logs: List[str]) -> List[Dict[str, Any]]:
        """分析网络日志"""
        issues = []
        
        for log in logs:
            if 'http://' in log.lower():
                issues.append({
                    "type": "HTTP 请求",
                    "severity": "中",
                    "description": f"检测到 HTTP 请求: {log[:100]}",
                    "recommendation": "建议使用 HTTPS"
                })
        
        return issues
    
    def _calculate_risk_level(self, issues: List[Dict[str, Any]]) -> str:
        """计算风险等级"""
        high_count = sum(1 for issue in issues if issue.get("severity") == "高")
        
        if high_count > 0:
            return "高"
        elif len(issues) > 0:
            return "中"
        else:
            return "低"

