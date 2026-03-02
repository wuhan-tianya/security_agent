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
- SSE 输出为模型真实流式返回，前端无需再分词模拟。

### 3.2 工具层
- 复用 `skills/scripts` 里的工具实现。
- 工具统一入口：`execute(**kwargs)`。
- 工具选择由模型基于工具描述做路由（支持多工具调用）。

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
- `mcp_call_started`（前端展示兼容事件名）
- `mcp_call_finished`（前端展示兼容事件名）
- `mcp_call_failed`（前端展示兼容事件名）
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

### 7.4 会话列表查询
- `GET /v1/sessions`
- 响应示例：
```json
{
  "sessions": [
    {
      "session_id": "session-xyz",
      "created_at": "2026-02-27T10:00:00",
      "updated_at": "2026-02-27T10:05:00"
    }
  ]
}
```

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

### 2026-02-27
- 新增 `/v1/sessions` 接口，支持获取历史会话列表。
- `skill_call_node` 增发 `mcp_call_*` 事件用于前端工具调用展示兼容。
- 记录发送给模型的完整 `messages` 到日志，便于排查提示词。
- 工具选择改为模型路由（OpenAI tools/tool_choice），支持多工具调用。
- 与大模型的交互改为流式输出，同时 SSE 直传模型流式 token。
- 流式返回为空时回退到非流式结果，确保对话内容写入数据库。
- 记录流式解析与工具调用异常到日志，便于排障与对齐 OpenAI 工具调用格式。
- 修复工具回传消息格式：透传路由阶段 assistant 的 `reasoning_content` 与 `tool_calls`，避免思考模型校验报错。
- 增加模型工具调用多轮循环：解析并执行模型返回的 `tool_calls`，回填 `role=tool` 结果后继续推理，直到得到最终回答。
- 增加 `content` 内嵌 `<function_calls>` 解析兼容，避免非结构化工具调用被忽略导致单轮结束。
- 新增内置工具 `generate_security_report`，真实写入 `backend/summaries`，并挂载 `/summaries` 静态访问。
- 工具 schema 改为根据 `execute` 签名自动生成，支持 `apk_path` 等必填参数。
- 报告生成后自动在最终回答追加可点击链接（绝对 URL），前端可直接打开报告页面。

### 2026-02-26
- 移除车机连接/引导与 MCP 调用链路。
- `/v1/vehicles` 接口下线，工具调用改为本地 `skills`。
- 更新 `/v1/tools` 返回本地技能清单。
- 更新文档与测试以匹配本地技能调用。
