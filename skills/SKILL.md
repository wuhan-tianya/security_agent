---
name: mobile-security-tools
description: 统一调用 Android 移动安全分析工具集合，覆盖 APK 基础信息、Manifest 配置、权限、网络、漏洞、静态扫描、动态扫描及 MobSF 集成功能。当任务涉及 tools 目录下 Python 工具的执行、封装、联调、排错或结果解读时使用。
---

# 移动安全工具总技能

使用 `scripts/` 下的 Python 脚本作为唯一实现来源，不再拆分多个独立 skill。

## 资源清单

- `scripts/apk_analyzer.py`: APK 基础信息、组件、证书分析
- `scripts/base_tool.py`: 统一工具抽象基类与结果格式
- `scripts/code_analyzer.py`: 调试信息、日志、混淆相关代码检查
- `scripts/dynamic_scanner.py`: 基于 Frida 的动态行为监控
- `scripts/manifest_analyzer.py`: AndroidManifest 安全配置分析
- `scripts/mobsf_integration.py`: MobSF 风格集成与工具路径解析
- `scripts/mobsf_static_analyzer.py`: MobSF 风格完整静态分析
- `scripts/network_analyzer.py`: 不安全网络通信与证书验证问题检测
- `scripts/permission_checker.py`: 危险权限识别与风险评级
- `scripts/static_scanner.py`: 全量静态扫描与风险汇总
- `scripts/vulnerability_scanner.py`: 常见漏洞模式扫描

## 执行流程

1. 根据用户任务选择对应脚本（单工具或组合调用）。
2. 优先使用各脚本中的 `execute(...)` 作为入口，保持返回结构一致：`success`、`data`、`error`。
3. 对依赖进行前置检查：`androguard`、`frida`、设备连接状态、APK 文件路径。
4. 输出时先给高风险项，再给计数汇总和修复建议。
5. 多工具联合分析时，按“基础信息 -> 配置面 -> 代码面 -> 运行时 -> 汇总结论”顺序组织结果。

## 结果约定

- 成功：返回结构化 `data`，保留原始字段命名，避免二次歧义翻译。
- 失败：返回明确 `error`，指出缺失依赖、无效输入或运行环境问题。
- 报告：优先呈现高危风险（如证书校验绕过、硬编码密钥、可导出高风险组件）。
