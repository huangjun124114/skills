# 安装与验收

## 交付结构

Skill ZIP 解压后应保持以下相对路径：

```text
yozuyun-analysis-skill/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── connection-and-clients.md
│   ├── runtime-and-cache.md
│   ├── workflow.md
│   ├── mcp-contract.md
│   ├── output-contract.md
│   ├── error-recovery.md
│   └── installation-and-acceptance.md
├── scripts/
│   ├── report_mcp.py
│   ├── report-mcp.ps1
│   └── report-mcp-macos.sh
└── assets/report-template.html
```

`SKILL.md` 是平台无关入口。`agents/openai.yaml` 是支持该元数据格式的宿主可选文件；不识别它的宿主可忽略。references、scripts 和 assets 的相对目录不能改变。全部协议、缓存与诊断逻辑在 `scripts/report_mcp.py`（Python 3.8+，仅标准库）；`report-mcp.ps1` 与 `report-mcp-macos.sh` 是薄启动器，仅探测解释器并透传参数，Windows 与 macOS 行为完全一致。宿主原生工具仍是首选入口。

## 宿主安装

宿主支持 ZIP 导入时，直接选择 `yozuyun-analysis-skill.zip`。宿主只支持目录时，解压后选择最外层 `yozuyun-analysis-skill` 文件夹。宿主只支持单份指令时，以 `SKILL.md` 为入口，同时将 references、scripts 和 assets 作为附件；若宿主无法执行附件脚本，则使用宿主原生 MCP 客户端。若宿主无法按需读取参考附件，至少合并 connection、runtime-and-cache、workflow、mcp-contract、output-contract 和 error-recovery 的内容。

安装 Skill 后仍需独立配置 MCP 连接：

1. 从业务系统管理员取得服务器地址和 API-Key。
2. 按 [connection-and-clients.md](connection-and-clients.md) 配置 Streamable HTTP 或 SSE。
3. 把 API-Key 放入 `X-API-Key` Header。
4. 刷新工具并确认三个工具可见。

## 兼容性声明

- 目标宿主：WorkBuddy、千问 Work、豆包工作，以及可读取 Markdown Skill 的同类桌面智能体。
- 目标系统：Windows 为主，macOS 为辅；运行前提是宿主机已安装 Python 3.8+（Windows 从 python.org，macOS 系统自带或经 Command Line Tools），不需要 pip、任何第三方包或包管理器。
- MCP 主协议：Streamable HTTP；兼容协议：SSE。
- MCP 工具契约：`2.0`。
- 宿主支持 `structuredContent` 时优先使用；仅支持文本 `content` 时仍可解析等价 JSON。
- 宿主能生成文件时支持 HTML 报告；PDF 取决于宿主的导出或打印能力。

## 核心验收场景

| 编号 | 场景 | 期望行为 |
|---|---|---|
| A1 | MCP 未连接，用户直接问数据 | 识别三工具不可见，给出地址、协议、Header 配置指引，不索要 API-Key 原文 |
| A2 | API-Key 无效 | 根据 `UNAUTHENTICATED/UPDATE_CONNECTION_CREDENTIAL` 指导更新连接凭据 |
| A3 | list 返回空目录 | 根据 `catalogState` 区分无授权与无 READY 报表 |
| A4 | 用户只问一个数字 | 完成 list→describe→analyze，直接给数字、单位、范围和口径，不生成报告 |
| A5 | 必填时间或组织缺失 | describe 后合并追问必要参数，不猜默认值 |
| A6 | 指标超过 3 个或有同比/环比 | 使用表格，标明单位、基期和计算方法 |
| A7 | 已出租间数、总运营间数、出租率 | 即使只有 3 个指标，也因指标关联使用表格 |
| A8 | 用户要求经营洞察报告 | 基于必要查询生成自包含 HTML，包含摘要、数据、洞察、口径和警告 |
| A9 | 定义版本变化 | 重新 describe 并重建查询，只重试一次 |
| A10 | 查询超限或 SQL 被拒绝 | 缩小范围或按 describe 重建查询，不绕过服务端限制 |
| A11 | 用户未要求趋势，当前结果也没有趋势 | 不为补充趋势新增报表或超过调用预算 |
| A12 | 报表开放/关闭发生变化 | 以最新 list 为准，Skill 无需改版或内置名单更新 |
| A13 | meta.application.displayName 为云掌柜 | 回答和 HTML 数据来源均使用云掌柜，不从安装名推断品牌 |
| A14 | 旧服务无 application 元数据 | 未指定业务系统时写“当前业务系统”；用户指定系统时先核对身份，再继续分析 |
| A15 | 用户处置后在新任务中改换业务应用连接 | 重新准入并 list/describe，使用本次响应名称，不复用其他应用上下文；不得在原任务中自行切换 |
| A16 | 新会话中存在历史工具定义 | 从当前有效 MCP 重新 tools/list，按实时 schema 调用，不使用历史定义 |
| A17 | 同一任务读取20分钟前缓存 | 校验 taskId、当前连接、实时 schema 和完整性后可用，并向用户报告时间水位 |
| A18 | 同一任务读取31分钟前缓存 | 默认拒绝并实时重查；只有用户明确要求旧数据时才允许，并标明已过期 |
| A19 | 新任务读取10分钟前缓存 | 拒绝跨任务缓存并重新获取，不接受改名、复制或复用旧 taskId |
| A20 | 宿主无原生调用入口但有当前 Streamable 配置 | 使用预置启动器完成握手、工具发现和调用，不现场重写客户端 |
| A21 | Windows 桌面智能体执行脚本 | 启动器经系统 PowerShell 5.1 定位 `py -3` / `python` 调用 Python 3.8+，不安装 Node.js、PowerShell 7 或任何 pip 包；缺少 Python 时停止并提示安装 |
| A22 | macOS 桌面智能体执行脚本 | 启动器经系统 `/bin/sh` 定位 `python3` 调用 Python 3.8+，不安装 Homebrew、jq 或任何 pip 包；缺少 Python 时停止并提示安装 |
| A23 | bootstrap 后工具 schema 变化 | 后续 call 的期望哈希校验失败，重新 bootstrap 并按新 schema 构造参数 |
| A24 | 请求需要逐项查询大量对象 | 禁止循环调用；优先聚合或批量查询，预计达到30次或数量未知时缩小范围 |
| A25 | 确实无法合并且预先确定需要12次调用 | 仍优先尝试缩减；必要时允许固定12次有限循环，不得动态增加或拆批规避上限 |
| A26 | 服务错误后建议重试 | 只按错误契约规定的次数重试，不进入循环、持续轮询或指数重试队列 |

更新已有安装时覆盖原 skill 或重新导入同名 ZIP；重连 MCP 并刷新工具缓存，在新对话验证，避免旧提示上下文残留。

## 通过标准

### 事故相关增量验收

| 编号 | 场景 | 通过条件 |
|---|---|---|
| B1 | 已选启用连接返回 HTTP 404 | 明确 Session not found 时按有限预算恢复，其他404或预算耗尽即停止；始终不试用其他连接 |
| B2 | 配置存在禁用条目或启用字段冲突 | disabled 为 true 或 enabled 为 false 均排除，禁用优先，不因可达而放行 |
| B3 | 用户业务口语对应多个口径 | analyze 前展示口径差异、选择理由并等待用户确认，保留原始单位 |
| B4 | 候选字段全为零或疑似未回填 | 如实标注异常与不确定性，不据此跳过澄清或替换口径 |
| B5 | 目标区间尚未结束 | 标注期间累计或月内累计及实际截止日，不与完整期间直接比较 |
| B6 | 输出业务数据或存在连接尝试异常 | 必须声明连接名称；披露切换、疑点和多次尝试，来源存疑时不输出结论 |
| B7 | 既有正确约束 | 缓存时效与任务隔离、预置脚本在线发现、空值及空结果处理、密钥保护和循环限制均保留 |
| B8 | 检查本次新增条款 | 不包含事故特定连接名、URL、业务月份、数值或报表编码 |

多个启用连接的选择按用户问题和当前连接信息进行；无法唯一确定时提问，不以逐个试连代替选择。

### 诊断能力增量验收

- 固定3组、最多9次请求，每组均验证 tools/list，不调用 tools/call。
- 输出状态分布、时间、session指纹；不因单次成功归因，不输出敏感原文。
- 会话404有限恢复覆盖：通知告警继续、第二/第三次成功、耗尽停止、普通404和鉴权错误不重试；校验原session、参数和协议头保持不变。

### 通用通过标准

- initialized 通知仅在明确 Session not found 404 时告警继续，其他错误停止；历史兼容开关不自动启用。
- 实际应用名称与用户指定系统不同或后续发生变化时，在下一次业务调用前停止；禁止用条目名、技术标识或解码密钥替代身份核对。
- 更新时核对实际加载路径，停用同用途的旧 Skill，避免旧版硬编码指令同时被加载；不自动删除用户目录。诊断材料与旧脚本不放入新安装包。

脚本回归入口为仓库 skills/tests/report-mcp-regression.cjs，不包含在安装包中；覆盖连接准入、任务绑定、协议解析与有限恢复。

- 不出现静态报表清单、虚构字段或虚构指标口径。
- API-Key 不进入聊天记录、Skill 文件、URL、日志或输出。
- 三工具顺序、参数通道、版本和错误恢复符合 MCP 2.0 契约。
- 简单问题直接回答，复杂对比使用表格，报告任务输出可独立打开的 HTML。
- 非用户明确需求的扩展不新引入逻辑表，接口调用不超过约定预算。
- 新会话仅使用当前有效连接和实时 schema；成功缓存固定30分钟、严格任务隔离，缓存回答完整披露时间水位。
- 不执行无界、未知数量或达到30次的循环工具调用；1–29次的确定有限循环仅作为无法批量处理时的例外，且不得动态扩大或拆分规避。
- `scripts/report_mcp.py` 通过 `python -m py_compile`，两个启动器分别通过 PowerShell 解析与 `sh -n` 语法检查，并以真实 Streamable HTTP 连接完成 bootstrap、call、同任务缓存命中、过期拒绝、跨任务拒绝和 schema 变化拒绝验收。
- WorkBuddy、千问 Work 和豆包工作至少各完成 A1、A4、A5、A8、A9 一次真实联调后再发布给终端用户；脚本模式还应分别在 Windows 与 macOS 完成 A20–A23。
