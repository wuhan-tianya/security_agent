# 安全智能体后端（FastAPI + LangGraph + uv）

## 1. 概述
后端基于本地 `skills/` 工具执行安全测试能力，不再提供车机连接/引导流程或 MCP 调用。

---

## 2. 关键接口与边界
1. 工具调用来源：`backend/skills/scripts` 本地工具。
2. LangGraph 节点：`skill_call_node` 负责本地工具执行。
3. `/v1/tools` 返回本地技能清单。

---

## 3. 架构设计

### 3.1 Agent 主服务
- FastAPI + LangGraph + SQLite memory + SSE。
- 负责会话、提示词、推理编排、工具调度、事件可观测。

### 3.2 工具层
- 复用 `skills/scripts` 里的工具实现。
- 工具统一入口：`execute(**kwargs)`。

### 3.3 调用流程
1. `classify_intent_node` 判定是否为安全测试意图。
2. `skill_call_node` 执行本地工具。
3. `reflect_node` 融合结果。
4. `memory_write_node` 写入记忆。

---

## 4. 提示词与策略
1. 提示词文件化（`backend/prompts/*`）。
2. 非安全意图不调用工具。

---

## 5. SSE 事件
- `skills_discovered`
- `skill_call_started`
- `skill_call_finished`
- `skill_call_failed`
- `llm_response`（模型输出摘要）

---

## 6. 失败策略
- 工具执行失败：`run_error` + `SKILL_CALL_FAILED`。

---

## 7. 接口说明

### 7.1 对话流式接口
- `POST /v1/chat/stream`

```json
{
  "session_id": "session-001",
  "user_input": "请做安全检查",
  "model": "gpt-4o-mini"
}
```

### 7.2 工具查询接口
- `GET /v1/tools`

响应示例：
```json
{
  "tools": [
    {
      "name": "apk_analyzer",
      "description": "分析 APK 文件的基本信息、组件、证书等"
    }
  ]
}
```

### 7.3 会话记忆查询
- `GET /v1/sessions/{session_id}/memory`

---

## 8. 配置（JSON）
默认配置文件：`backend/config/settings.json`。

可配置项：
- `app_name`
- `db_path`
- `llm_base_url`
- `llm_api_key`
- `llm_model`
- `llm_timeout_seconds`
- `default_system_prompt_file`
- `default_user_prompt_file`
- `default_tool_policy_file`

---

## 9. 改动记录

### 2026-02-26
- 移除车机连接/引导与 MCP 调用链路。
- `/v1/vehicles` 接口下线，工具调用改为本地 `skills`。
- 更新 `/v1/tools` 返回本地技能清单。
- 更新文档与测试以匹配本地技能调用。
