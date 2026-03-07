# Security Agent 项目架构分析

## 项目概述

一个**车载安全智能体系统**，基于 LLM 驱动的安全测试工具编排，提供对话式安全检测能力。

| 层级 | 技术栈 | 职责 |
|------|--------|------|
| 前端 | React + Vite + TypeScript + TailwindCSS | 聊天式交互界面 |
| 后端 | FastAPI + LangGraph + SQLite | Agent 编排、工具调度、会话记忆 |
| 工具层 | Python 脚本（10 个安全工具） | APK 分析、漏洞扫描、网络分析等 |

---

## 项目目录结构

```
security_agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── api/v1/              # REST 接口（chat, sessions, tools）
│   │   ├── graph/               # LangGraph 图编排
│   │   │   ├── builder.py       # 图构建（节点 + 边）
│   │   │   ├── nodes.py         # 6 个节点函数
│   │   │   ├── state.py         # AgentState 定义
│   │   │   └── events.py        # SSE 事件工具
│   │   ├── services/
│   │   │   └── agent_service.py # 核心服务：SSE 流式 + 工具调用循环
│   │   ├── skills/registry.py   # 工具注册中心
│   │   ├── memory/repository.py # SQLite 会话记忆
│   │   ├── prompts/             # 提示词加载 & 渲染
│   │   ├── llm/                 # OpenAI 兼容客户端
│   │   ├── core/config.py       # 配置管理
│   │   └── db/database.py       # SQLite 封装
│   ├── skills/scripts/          # 10 个安全测试工具实现
│   ├── prompts/                 # 提示词模板文件
│   └── config/settings.json     # 运行配置
└── frontend/
    └── src/
        ├── App.tsx              # 根组件
        ├── main.tsx             # 入口
        ├── api/index.ts         # 后端 API 调用
        ├── features/chat/
        │   └── ChatWindow.tsx   # 核心聊天窗口（SSE 消费）
        └── components/layout/   # Header, Sidebar, MainLayout
```

---

## 核心架构流程图

### 1. 整体系统架构

```mermaid
graph TB
    subgraph Frontend["前端 (React + Vite)"]
        UI["ChatWindow.tsx<br/>聊天界面"]
        API["api/index.ts<br/>API 客户端"]
    end

    subgraph Backend["后端 (FastAPI)"]
        Router["API Router<br/>/v1/chat/stream<br/>/v1/tools<br/>/v1/sessions"]
        Service["AgentService<br/>SSE 流式 + 工具循环"]
        Graph["LangGraph<br/>Agent 状态图"]
        Memory["Repository<br/>SQLite 记忆"]
        Skills["SkillRegistry<br/>工具注册中心"]
        LLM["OpenAI Client<br/>LLM 推理"]
        Prompts["PromptLoader<br/>提示词模板"]
    end

    subgraph Tools["安全工具层 (skills/scripts)"]
        T1["apk_analyzer"]
        T2["static_scanner"]
        T3["dynamic_scanner"]
        T4["vulnerability_scanner"]
        T5["manifest_analyzer"]
        T6["其他工具..."]
    end

    UI -->|"SSE 请求"| API
    API -->|"POST /v1/chat/stream"| Router
    Router --> Service
    Service --> Graph
    Graph --> Memory
    Graph --> Skills
    Graph --> LLM
    Graph --> Prompts
    Skills --> T1 & T2 & T3 & T4 & T5 & T6
```

### 2. LangGraph Agent 处理流程

```mermaid
graph TD
    Start(["用户输入"]) --> LP["load_prompt<br/>加载提示词模板"]
    LP --> MR["memory_read<br/>读取历史上下文<br/>(最近 30 条消息)"]
    MR --> CI["classify_intent<br/>意图分类<br/>判断是否为安全测试"]
    CI --> SC["skill_call<br/>模型路由选择工具<br/>执行本地安全工具"]
    SC --> RF["reflect<br/>融合工具结果<br/>生成最终回答"]
    RF --> MW["memory_write<br/>写入会话记忆"]
    MW --> End(["返回结果"])

    style Start fill:#4ade80,stroke:#22c55e,color:#000
    style End fill:#4ade80,stroke:#22c55e,color:#000
    style LP fill:#60a5fa,stroke:#3b82f6,color:#000
    style MR fill:#60a5fa,stroke:#3b82f6,color:#000
    style CI fill:#f97316,stroke:#ea580c,color:#000
    style SC fill:#f43f5e,stroke:#e11d48,color:#fff
    style RF fill:#a78bfa,stroke:#8b5cf6,color:#000
    style MW fill:#60a5fa,stroke:#3b82f6,color:#000
```

### 3. SSE 流式对话完整链路

```mermaid
sequenceDiagram
    participant U as 前端 ChatWindow
    participant A as API Router
    participant S as AgentService
    participant G as LangGraph
    participant L as LLM (OpenAI)
    participant T as 安全工具

    U->>A: POST /v1/chat/stream
    A->>S: stream_sse_events()
    S->>G: 运行 Agent 图

    G->>G: load_prompt → 加载提示词
    G->>G: memory_read → 读取历史
    G->>L: classify_intent → 意图分类
    L-->>G: 返回意图结果

    alt 安全测试意图
        G->>L: skill_call → 请求工具路由
        L-->>G: tool_calls (选择工具)
        loop 多轮工具调用
            G->>T: 执行工具
            T-->>G: 工具结果
            S-->>U: SSE: skill_call_started/finished
        end
    end

    G->>L: reflect → 融合结果生成回答
    L-->>S: 流式 token
    S-->>U: SSE: llm_token (逐 token)
    G->>G: memory_write → 持久化
    S-->>U: SSE: run_finished
```

### 4. 安全工具清单

| 工具 | 文件 | 功能 |
|------|------|------|
| `apk_analyzer` | [apk_analyzer.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/apk_analyzer.py) | APK 基本信息、组件、证书分析 |
| `static_scanner` | [static_scanner.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/static_scanner.py) | 静态代码安全扫描 |
| `dynamic_scanner` | [dynamic_scanner.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/dynamic_scanner.py) | 动态行为安全扫描 |
| `vulnerability_scanner` | [vulnerability_scanner.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/vulnerability_scanner.py) | 已知漏洞检测 |
| `manifest_analyzer` | [manifest_analyzer.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/manifest_analyzer.py) | AndroidManifest 分析 |
| `mobsf_integration` | [mobsf_integration.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/mobsf_integration.py) | MobSF 集成 |
| `mobsf_static_analyzer` | [mobsf_static_analyzer.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/mobsf_static_analyzer.py) | MobSF 静态分析 |
| `network_analyzer` | [network_analyzer.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/network_analyzer.py) | 网络通信安全分析 |
| `permission_checker` | [permission_checker.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/permission_checker.py) | 权限合规检查 |
| `code_analyzer` | [code_analyzer.py](file:///Users/xiongdejian/project/python_project/security_agent/backend/skills/scripts/code_analyzer.py) | 源码安全分析 |

### 5. 后端关键模块依赖关系

```mermaid
graph LR
    main["main.py<br/>FastAPI App"] --> router["api/v1/<br/>API 路由"]
    main --> service["AgentService<br/>核心服务"]

    service --> graph["LangGraph<br/>图编排"]
    service --> registry["SkillRegistry<br/>工具注册"]
    service --> llm["OpenAI Client"]
    service --> prompt["PromptLoader"]
    service --> repo["Repository"]

    graph --> nodes["nodes.py<br/>6 个节点"]
    nodes --> registry
    nodes --> llm
    nodes --> repo
    nodes --> prompt

    registry --> tools["skills/scripts/<br/>10 个安全工具"]
    repo --> db["Database<br/>SQLite"]

    style main fill:#fbbf24,stroke:#f59e0b,color:#000
    style service fill:#f87171,stroke:#ef4444,color:#000
    style graph fill:#a78bfa,stroke:#8b5cf6,color:#000
    style registry fill:#34d399,stroke:#10b981,color:#000
```

---

## API 接口一览

| 接口 | 方法 | 描述 |
|------|------|------|
| `/v1/chat/stream` | POST | 对话流式接口（SSE） |
| `/v1/tools` | GET | 查询可用工具清单 |
| `/v1/sessions` | GET | 获取历史会话列表 |
| `/v1/sessions/{id}/memory` | GET | 查询会话记忆 |
| `/healthz` | GET | 健康检查 |
| `/summaries/*` | Static | 安全报告静态文件 |
