"""
代码分析工具
分析代码质量、混淆情况等
"""
import re
from typing import Dict, Any, List
from .base_tool import BaseTool


class CodeAnalyzer(BaseTool):
    """代码分析工具"""
    
    def __init__(self):
        super().__init__(
            name="code_analyzer",
            description="分析代码质量、混淆情况、调试信息等"
        )
    
    def execute(self, code_content: str = None, apk_path: str = None, **kwargs) -> Dict[str, Any]:
        """
        分析代码
        
        Args:
            code_content: 代码内容（可选）
            apk_path: APK 文件路径（可选）
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        findings = []
        
        if code_content:
            findings.extend(self._check_debug_info(code_content))
            findings.extend(self._check_logging(code_content))
            findings.extend(self._check_proguard(code_content))
        
        result = {
            "success": True,
            "data": {
                "findings": findings,
                "total_count": len(findings),
                "recommendations": self._generate_recommendations(findings)
            }
        }
        
        return result
    
    def _check_debug_info(self, content: str) -> List[Dict[str, Any]]:
        """检查调试信息"""
        findings = []
        
        # 检查是否包含调试标志
        debug_patterns = [
            r'android:debuggable\s*=\s*["\']true["\']',
            r'BuildConfig\.DEBUG',
        ]
        
        for pattern in debug_patterns:
            if re.search(pattern, content):
                findings.append({
                    "type": "调试信息",
                    "severity": "中",
                    "description": "发现调试相关的代码或配置",
                    "recommendation": "生产环境应禁用调试功能"
                })
                break
        
        return findings
    
    def _check_logging(self, content: str) -> List[Dict[str, Any]]:
        """检查日志输出"""
        findings = []
        
        # 检查敏感信息日志
        sensitive_log_patterns = [
            r'Log\.(d|e|i|v|w)\s*\([^,]+,\s*["\'].*(password|token|key|secret)',
        ]
        
        for pattern in sensitive_log_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append({
                    "type": "敏感信息日志",
                    "severity": "高",
                    "description": "发现可能记录敏感信息的日志代码",
                    "recommendation": "移除或加密敏感信息的日志输出"
                })
                break
        
        return findings
    
    def _check_proguard(self, content: str) -> List[Dict[str, Any]]:
        """检查代码混淆"""
        findings = []
        
        # 检查是否有混淆配置
        if 'proguard' in content.lower() or 'minifyEnabled' in content:
            findings.append({
                "type": "代码混淆",
                "severity": "信息",
                "description": "检测到代码混淆配置",
                "recommendation": "确保生产版本启用了代码混淆"
            })
        else:
            findings.append({
                "type": "代码混淆",
                "severity": "中",
                "description": "未检测到代码混淆配置",
                "recommendation": "建议启用代码混淆以保护应用"
            })
        
        return findings
    
    def _generate_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        """生成建议"""
        recommendations = []
        for finding in findings:
            rec = finding.get("recommendation")
            if rec and rec not in recommendations:
                recommendations.append(rec)
        return recommendations

