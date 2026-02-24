"""
权限检查工具
检查 APK 申请的权限，识别危险权限
"""
from typing import Dict, Any, List, Optional
from .base_tool import BaseTool

# 危险权限列表
DANGEROUS_PERMISSIONS = [
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_PHONE_STATE",
    "android.permission.CALL_PHONE",
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.READ_CALENDAR",
    "android.permission.WRITE_CALENDAR",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.CAMERA",
    "android.permission.RECORD_AUDIO",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
]


class PermissionChecker(BaseTool):
    """权限检查工具"""
    
    def __init__(self):
        super().__init__(
            name="permission_checker",
            description="检查 APK 申请的权限，识别危险权限"
        )
    
    def execute(self, permissions: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        """
        检查权限
        
        Args:
            permissions: 权限列表
            
        Returns:
            Dict[str, Any]: 检查结果
        """
        if not permissions:
            return {
                "success": False,
                "error": "权限列表为空",
                "data": {}
            }
        
        dangerous_perms = []
        normal_perms = []
        
        for perm in permissions:
            if perm in DANGEROUS_PERMISSIONS:
                dangerous_perms.append(perm)
            else:
                normal_perms.append(perm)
        
        result = {
            "success": True,
            "data": {
                "total_permissions": len(permissions),
                "dangerous_permissions": dangerous_perms,
                "dangerous_count": len(dangerous_perms),
                "normal_permissions": normal_perms,
                "normal_count": len(normal_perms),
                "risk_level": self._calculate_risk_level(len(dangerous_perms))
            }
        }
        
        return result
    
    def _calculate_risk_level(self, dangerous_count: int) -> str:
        """计算风险等级"""
        if dangerous_count == 0:
            return "低"
        elif dangerous_count <= 3:
            return "中"
        elif dangerous_count <= 6:
            return "高"
        else:
            return "极高"
