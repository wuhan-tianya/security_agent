# 车机安全智能体 MCP 改造方案（FastAPI + LangGraph + uv）

## 1. 概述
将现有“本地 Python `execute` 直调”改为 **MCP 调用**，目标如下：

1. 全量工具迁移到 MCP（不保留旧直调链路）。
2. 同时支持 `stdio` 本地 MCP 与远程 HTTP MCP。
3. MCP Server 使用独立仓库维护。
4. MCP 失败采用快速失败策略（不降级纯 LLM）。

---

## 2. 关键接口与边界变更

1. Agent 后端不再直接导入 `skills/scripts` 工具类。
2. 新增 MCP 客户端抽象：
   - `MCPClient`（统一接口）
   - `StdioMCPClient`
   - `HttpMCPClient`
3. LangGraph 中 `tool_exec_node` 替换为 `mcp_call_node`。
4. `/v1/tools` 改为返回 MCP 动态发现结果。
5. 新增配置项：
   - `MCP_MODE=stdio|http|hybrid`
   - `MCP_SERVERS=[...]`（多 server，含地址/命令/超时）

---

## 3. 架构设计

### 3.1 Agent 主仓库
- FastAPI + LangGraph + SQLite memory + SSE。
- 负责会话、提示词、推理编排、MCP 调度、事件可观测。

### 3.2 MCP 独立仓库
- 将安全工具包装为 MCP tools。
- 每个 tool 提供标准输入 schema 与结构化输出。
- 工具逻辑沿用原有实现。

### 3.3 调用流程
1. `planner_llm_node` 产出工具意图  
2. `mcp_router_node` 选择 server/tool  
3. `mcp_call_node` 调用 `tools/call`  
4. `reflect_node` 融合结果  
5. `memory_write_node` 写入记忆  

---

## 4. 提示词与策略
1. 提示词继续后端文件化管理（仅配置文件）。
2. 工具调用策略改为 MCP 约束：
   - 仅基于 `tools/list` 的真实能力选工具
   - 参数严格匹配 schema
   - MCP 调用失败立即终止当前 run

---

## 5. SSE 事件扩展
保留原事件并新增：

1. `mcp_server_selected`
2. `mcp_tools_discovered`
3. `mcp_call_started`
4. `mcp_call_finished`
5. `mcp_call_failed`

---

## 6. 失败与超时策略
1. 任一关键 MCP 调用失败：返回 `run_error`。
2. 错误码建议：
   - `MCP_UNAVAILABLE`
   - `MCP_TIMEOUT`
   - `MCP_SCHEMA_ERROR`
3. 不进行纯 LLM 降级回答，避免安全误导。
4. 默认工具超时 30s，可按工具覆盖。

---

## 7. 实施拆解

### 7.1 Agent 仓库改造
- 新增 `app/mcp/*`（client、router、schema、healthcheck）。
- 替换图中工具执行节点。
- `/v1/tools` 改为 MCP 动态聚合。
- 增加 MCP 配置与启动健康检查。

### 7.2 MCP 独立仓库建设
- 建立 MCP server 骨架与工具注册中心。
- 接入安全工具并定义输入/输出 schema。
- 提供 `stdio` 与 HTTP 两种入口。

### 7.3 联调
- Hybrid 模式同名工具冲突处理（优先级规则）。
- 端到端验证 SSE、记忆、工具调用、错误路径。

---

## 8. 测试与验收

### 8.1 单元测试
- MCP client 连接、重试、超时。
- schema 校验与参数拒绝。
- server 选择策略。

### 8.2 集成测试
- `stdio` 模式完整调用成功。
- HTTP 模式完整调用成功。
- MCP 不可用时快速失败且不输出业务结论。

### 8.3 验收标准
1. 所有工具调用均走 MCP，无直调残留。
2. `/v1/tools` 反映实时 MCP 工具清单。
3. SSE 可见完整 MCP 调用链路。
4. `session_id` 维度记忆连续生效。

---

## 9. 假设
1. Agent 与 MCP server 网络可达。
2. MCP 独立仓库由你方维护工具实现细节。
3. 当前阶段不引入复杂鉴权，后续可扩展 token/mTLS。

---

## 10. 多车机远程路由补充（按 IP）

1. 用户自然语言指定某车机 IP，直接连接该 IP 对应 MCP。
2. 用户未指定 IP，智能体先返回候选车机列表并引导选择。
3. 车机未完成 MCP 配置时，返回明确配置指引（endpoint/认证/连通性）。
4. 关键错误码：
   - `VEHICLE_NOT_SELECTED`
   - `VEHICLE_NOT_REGISTERED`
   - `VEHICLE_NOT_CONFIGURED`
   - `MCP_CONNECT_TIMEOUT`
   - `MCP_UNAVAILABLE`

---

## 11. 接口说明文档（当前实现）

### 11.1 健康检查

- `GET /healthz`
- 响应示例：

```json
{
  "ok": true
}
```

### 11.2 对话流式接口

- `POST /v1/chat/stream`
- Content-Type: `application/json`
- 请求体：

```json
{
  "session_id": "session-001",
  "user_input": "请连接 10.1.1.2 并做安全检查",
  "target_vehicle_ip": "10.1.1.2",
  "model": "gpt-4o-mini"
}
```

- 返回：`text/event-stream`
- 事件顺序（按场景有分支）：
  - `run_started`
  - `prompt_loaded`
  - `memory_read`
  - `vehicle_ip_parsed`
  - `vehicle_connected` 或 `vehicle_selection_required` 或 `vehicle_unconfigured`
  - `mcp_tools_discovered`（仅 vehicle_ready）
  - `mcp_call_started`（仅 vehicle_ready）
  - `mcp_call_finished` 或 `mcp_call_failed`
  - `reasoning_trace`
  - `memory_write`
  - `llm_token`（按最终文本切词推送）
  - `run_error`（失败时）
  - `run_finished`

### 11.3 工具查询接口

- `GET /v1/tools`
- Query 参数：
  - `ip`（可选）：只看指定车机工具
- 响应示例：

```json
{
  "tools": [
    {
      "vehicle_name": "car-a",
      "ip": "10.1.1.2",
      "name": "apk_analyzer",
      "description": "APK analyzer",
      "input_schema": {},
      "source_endpoint": "http://10.1.1.2:9000"
    }
  ]
}
```

### 11.4 会话记忆查询

- `GET /v1/sessions/{session_id}/memory`
- 响应示例：

```json
{
  "session_id": "session-001",
  "recent_messages": [],
  "latest_summary": null,
  "last_vehicle_ip": "10.1.1.2"
}
```

### 11.5 会话重置

- `POST /v1/sessions/{session_id}/reset`
- 响应示例：

```json
{
  "ok": true,
  "session_id": "session-001"
}
```

### 11.6 车机注册表查询

- `GET /v1/vehicles`
- 响应示例：

```json
{
  "vehicles": [
    {
      "vehicle_name": "car-a",
      "ip": "10.1.1.2",
      "mcp_endpoint": "http://10.1.1.2:9000",
      "status": "online",
      "is_configured": true,
      "last_seen_at": null
    }
  ]
}
```

### 11.7 车机注册表新增/更新

- `POST /v1/vehicles`
- 请求体：

```json
{
  "vehicle_name": "car-a",
  "ip": "10.1.1.2",
  "mcp_endpoint": "http://10.1.1.2:9000",
  "status": "online",
  "is_configured": true,
  "auth_type": "none",
  "auth_secret_ref": null
}
```

- 响应示例：

```json
{
  "ok": true
}
```

### 11.8 运行时配置（JSON）

- 默认配置文件：`backend/config/settings.json`
- 可配置项（当前实现）：
  - `app_name`
  - `db_path`
  - `llm_base_url`
  - `llm_api_key`
  - `llm_model`
  - `llm_timeout_seconds`
  - `mcp_mode`
  - `mcp_timeout_seconds`
  - `default_system_prompt_file`
  - `default_user_prompt_file`
  - `default_tool_policy_file`
- 覆盖优先级：
  1. 默认值
  2. JSON 配置文件
  3. 环境变量（最高优先级）
- 可通过 `CONFIG_FILE` 指定非默认 JSON 文件路径。

---

## 12. SSE 事件字典（当前实现）

- `vehicle_ip_parsed`：从自然语言中提取到的 IP（可能为 `null`）。
- `vehicle_selection_required`：未指定车机或 IP 未注册，附带候选车机列表。
- `vehicle_unconfigured`：车机存在但未完成 MCP 配置。
- `vehicle_connected`：车机校验通过，可执行 MCP 调用。
- `vehicle_connect_failed`：车机连接失败（例如超时/不可达）。
- `mcp_tools_discovered`：目标车机暴露的工具列表。
- `mcp_call_started`：开始调用 MCP 工具。
- `mcp_call_finished`：MCP 调用成功。
- `mcp_call_failed`：MCP 调用失败。
- `run_error`：本次运行失败，包含 `error_code` 和 `message`。

---

## 13. 文档维护要求（强制）

后续每次代码改动，必须同步更新本文件并追加到“14. 改动记录”，至少包含：

1. 改动日期（YYYY-MM-DD）。
2. 改动文件路径。
3. 改动点摘要（接口、字段、事件、错误码、行为变化）。
4. 兼容性影响（有/无）。

---

## 14. 改动记录

### 2026-02-24

- 新增后端骨架：`app/`、`prompts/`、`tests/`、`pyproject.toml`。
- 新增多车机路由能力：自然语言 IP 解析、车机注册表校验、分支引导节点。
- 新增数据库表：`vehicles`，并在 `sessions` 增加 `last_vehicle_ip` 字段。
- 新增 MCP 客户端层：HTTP/stdio/hybrid 路由。
- 新增 SSE 事件：`vehicle_ip_parsed`、`vehicle_selection_required`、`vehicle_unconfigured`、`vehicle_connected`、`vehicle_connect_failed`、`mcp_call_*`。
- 新增接口：`/v1/chat/stream`、`/v1/tools`、`/v1/vehicles`、`/v1/sessions/{session_id}/memory`、`/v1/sessions/{session_id}/reset`。
- 新增测试：`tests/test_vehicle_routing.py`，覆盖 5 个核心场景。
- 更新 `README.md`：补充 `uv` 启动、健康检查、车机注册、流式调用与测试命令。
- 新增 JSON 配置：`config/settings.json`，用于模型与 MCP 等运行参数配置。
- 更新配置加载器：`app/core/config.py` 支持“默认值 + JSON + 环境变量覆盖”。
- 新增测试：`tests/test_config_json.py`，验证 JSON 生效与环境变量覆盖优先级。
- 新增 `.gitignore`：忽略 Python 缓存、虚拟环境、测试缓存、IDE 文件、本地数据库和本地敏感配置覆盖文件。
- 新增本地 MCP 工具服务：`app/mcp/local_server.py`，提供 `/tools/list` 与 `/tools/call` 供本地联调。
- 修复 LangGraph 节点注册：`app/graph/builder.py` 改为异步包装函数，避免 coroutine 未 await 导致 `/v1/chat/stream` 在 `run_started` 后中断。
- 目录重构：后端代码迁移至 `backend/`（`app/`、`config/`、`prompts/`、`tests/`、`pyproject.toml`、`uv.lock`）。
- 新增后端启动脚本：`backend/start_backend.sh`，用于一键 `uv sync` + `uvicorn` 启动。
- 更新 `.gitignore`：增加 `backend/data/*.db` 与 `backend/config/settings.local.json` 忽略规则。
- 修复提示词路径加载：`backend/app/prompts/loader.py` 增加相对路径自动解析到 `backend/` 根目录，避免在仓库根目录启动时报 `prompts/system.md` 不存在。
- 新增测试：`backend/tests/test_prompt_loader_paths.py`，验证不同启动目录下提示词文件可正确加载。
- 目录迁移：`skills/` 移动到 `backend/skills/`；根目录 `data/` 合并到 `backend/data/`（保留原 backend 数据库，同时迁移根目录数据库为 `backend/data/security_agent.from_root.db`）。
- 新增 MCP 启动脚本：`backend/start_mcp.sh`，支持通过 `MCP_HOST`/`MCP_PORT` 启动本地 `app.mcp.local_server`。
- 修复 MCP HTTP 客户端：`backend/app/mcp/client.py` 禁用环境代理（`trust_env=False`），避免 localhost/private IP 被系统代理转发导致 `502 Bad Gateway`；并增强 HTTP 错误信息输出（状态码+响应体摘要）。
- 改进 LLM 调用稳定性：`backend/app/llm/openai_compatible.py` 禁用环境代理并增强 HTTP 错误提示；`backend/app/graph/nodes.py` 增加模型总结失败时的本地工具结果摘要兜底，避免把异常原文直接返回给用户。
- 更新 `backend/README.md`：补充 Kimi/OpenAI-Compatible 的 `llm_base_url` 与 `403 Forbidden` 排查说明。
- 改进车机选择逻辑：`backend/app/graph/nodes.py` 仅允许选择在线车机；无显式选择时优先匹配车机名称或复用会话 `last_vehicle_ip`，实现多轮对话持续使用已选车机；新增测试覆盖名称匹配与复用逻辑。
- 调整车机选择入口：`backend/app/api/schemas.py` 增加 `target_vehicle_ip` 字段；`backend/app/graph/nodes.py` 仅接受接口传入 IP 作为选择，未选择时提示；支持复用会话 `last_vehicle_ip` 以实现多轮对话。
- 兼容前端字段：`backend/app/api/schemas.py` 增加 `vehicle_ip` 兼容字段；`backend/app/api/routes_chat.py` 允许 `vehicle_ip` 回退到 `target_vehicle_ip`，避免前端字段不一致导致反复提示未选车机。
- 增加安全意图门控：`backend/app/graph/nodes.py` 仅在用户意图与安全测试相关时调用 MCP；新增测试覆盖非安全意图时跳过 MCP。
- 改用模型分类器：`backend/app/graph/nodes.py` 通过 LLM 二分类判断安全测试意图，非安全意图不调用 MCP；`backend/app/graph/builder.py` 新增分类节点；测试用例显式设置 `security_intent` 以避免外部 LLM 依赖。
- 兼容性影响：无（新仓库初始实现）。
