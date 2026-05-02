# 🏥 医院智能排班与调班助手

基于 **LLM + OR-Tools (CP-SAT)** 的医院智能排班 Agent，支持**自然语言交互**，覆盖排班生成、调班、冲突检测、紧急代班、工作量分析等全流程。提供 CLI 命令行和 Web 管理界面两种使用方式。

## ✨ 功能特性

### 📅 排班管理

| 功能 | 说明 |
|------|------|
| **自动排班生成** | 基于 OR-Tools 约束求解器，自动生成满足约束的排班表 |
| **智能调班** | 员工可通过自然语言发起调班请求 |
| **排班查询** | 按员工、日期、班次类型多维度查询排班信息 |

### 🧠 智能技能

| 技能 | 说明 |
|------|------|
| **冲突检测** | 自动检测连续排班超标、夜班过多、技能不匹配等违规 |
| **紧急代班** | 当员工请假/生病时，综合技能、工作量、偏好推荐最佳替代人员 |
| **工作量分析** | 统计排班分布、公平性评估（变异系数）、个人工作量排名 |
| **质量评估** | 多维度评分（覆盖率/技能匹配/合规率/均衡性），给出 A-D 等级 |
| **偏好学习** | 从自然语言中学习并记录员工排班偏好，后续排班自动参考 |

### 💬 交互体验

- **Web 管理界面** — 清新的可视化仪表盘，支持所有操作
- **自然语言意图识别** — LLM 自动理解用户意图
- **对话记忆** — 自动记录上下文，支持连贯对话
- **通用对话** — 日常闲聊与排班知识咨询

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 编程语言 | Python 3.10+ |
| 约束求解 | OR-Tools CP-SAT |
| LLM 推理 | SiliconFlow API（兼容 OpenAI 格式） |
| Web 框架 | FastAPI + Uvicorn |
| 数据处理 | pandas, openpyxl |
| 前端 | HTML + CSS + JavaScript（无框架依赖） |
| 数据存储 | Excel + JSON |

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Aurora-da/-.git
cd repo
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API 密钥

复制 `.env.example` 为 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
SILICONFLOW_API_KEY=your_api_key_here
SILICONFLOW_MODEL=Qwen/Qwen3-Next-80B-A3B-Instruct
```

> 默认使用 SiliconFlow 的免费模型 Qwen3-Next-80B-A3B-Instruct，仅需配置 API Key。

### 4. 准备数据

确保 `agent/data/` 目录下有以下 Excel 文件：

| 文件 | 说明 |
|------|------|
| `staff_info.xlsx` | 员工信息（姓名、角色、技能等级、可用日期） |
| `shift_config.xlsx` | 班次配置（日期、班次类型、所需人数、技能要求） |

### 5. 启动方式

#### 🐳 Docker 一键部署（推荐）

```bash
# 1. 配置 API Key
cp .env.example .env
# 编辑 .env，填入真实的 SILICONFLOW_API_KEY

# 2. 一键启动
docker compose up -d

# 3. 访问 http://localhost:8000
```

> 排班结果文件持久化在 `agent/data/` 目录，容器重启不会丢失。

#### 🌐 本地手动启动

```bash
python run_api.py
```

访问 `http://localhost:8000` 进入可视化操作界面。

#### 💻 CLI 命令行

```bash
python run_cli.py
```

## 💡 使用示例

启动后通过自然语言输入指令：

```text
# 排班生成
生成排班表

# 调班请求
张医生2024-10-03夜班想调班

# 排班查询
查询李护士2024-10-01的排班

# 冲突检测
检测当前排班有没有冲突

# 紧急代班
张医生明天夜班生病了，找人代班

# 工作量分析
分析一下大家的工作量是否均衡

# 质量评估
评估当前排班表的质量

# 偏好学习
李医生希望周一和周三上早班

# 查看偏好
查看所有员工的偏好记录
```

## 🌐 API 接口

启动 Web 服务后，自动提供 RESTful API：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/staff` | 获取员工列表 |
| GET | `/api/shifts` | 获取班次配置 |
| GET | `/api/schedule` | 查看当前排班 |
| POST | `/api/schedule/generate` | 生成排班 |
| POST | `/api/schedule/swap` | 调班处理 |
| POST | `/api/schedule/query` | 查询排班 |
| GET | `/api/conflicts` | 冲突检测 |
| POST | `/api/emergency/substitute` | 紧急代班 |
| GET | `/api/workload` | 工作量分析 |
| GET | `/api/quality` | 质量评估 |
| GET | `/api/preferences` | 查看偏好 |
| POST | `/api/preferences/learn` | 学习偏好 |
| POST | `/api/chat` | AI 对话 |

查看完整 API 文档：启动后访问 `http://localhost:8000/docs`

## 📁 项目结构

```text
├── run_api.py              # Web 服务启动入口
├── run_cli.py              # CLI 命令行启动入口
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── .gitignore
│
├── agent/                  # 核心智能体逻辑
│   ├── main.py             # CLI 交互主循环
│   ├── agent.py            # 意图识别（LLM）
│   ├── config.py           # 配置项和常量
│   ├── llm_client.py       # LLM API 客户端
│   ├── scheduler.py        # 排班求解器（OR-Tools）
│   ├── swap_solver.py      # 调班求解器
│   ├── skills.py           # 5大智能技能模块
│   ├── excel_loader.py     # Excel 数据加载
│   ├── excel_exporter.py   # Excel 结果导出
│   ├── chat_tools.py       # 对话记忆管理
│   ├── doctor_scheduling_data.json
│   └── data/
│       ├── staff_info.xlsx
│       └── shift_config.xlsx
│
├── backend/                # FastAPI 后端
│   ├── __init__.py
│   ├── main.py             # 应用入口
│   ├── routes.py           # API 路由
│   └── schemas.py          # 数据模型
│
└── frontend/               # Web 前端
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

## ⚙️ 核心配置

在 `agent/config.py` 中可自定义：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_CONSECUTIVE_SHIFTS` | 2 | 最大连续排班天数 |
| `MAX_NIGHT_SHIFTS_PER_PERSON` | 3 | 每人最大夜班次数 |
| `WORKLOAD_FAIRNESS_EXCELLENT` | 15% | 公平性优秀阈值（变异系数） |
| `LLM_MAX_RETRIES` | 3 | LLM 调用最大重试次数 |
| `MAX_MEMORY_LENGTH` | 10 | 对话记忆最大条数 |

## 📊 排班规则说明

系统默认约束包括：

- 每人每天最多一个班次
- 连续排班不超过 `MAX_CONSECUTIVE_SHIFTS` 天
- 每人夜班不超过 `MAX_NIGHT_SHIFTS_PER_PERSON` 次
- 员工技能等级需满足班次要求
- 优先分配可用日期内的员工
- 支持按科室/部门匹配，护理部可跨科调配

## 📝 License

MIT
