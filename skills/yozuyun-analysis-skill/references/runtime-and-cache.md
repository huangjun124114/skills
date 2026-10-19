# 运行脚本与缓存规则

## 执行入口

当前宿主已原生提供 MCP 工具时，直接使用宿主工具，并以当前会话显示的 schema 为准。WorkBuddy、千问 Work、豆包工作等宿主没有暴露可调用工具、但能读取当前 Streamable HTTP 连接配置时，按操作系统使用预置启动器。不要为同一协议重新编写连接、握手、工具发现或缓存脚本。

全部协议、缓存与诊断逻辑集中在单一 Python 核心脚本 `scripts/report_mcp.py`（Python 3.8+，仅标准库）；`report-mcp.ps1` 与 `report-mcp-macos.sh` 只是薄启动器，负责定位 Python 解释器并透传参数，Windows 与 macOS 行为完全一致。运行前提是宿主机已安装 Python 3.8+（无需 pip、无需任何第三方包）；缺少 Python 时启动器会停止并提示安装，不得为此改用其他语言重写客户端。它们完成：

- `initialize` 和 `notifications/initialized` 握手；
- 在线 `tools/list`；固定三工具服务意外分页时停止，不循环探测；
- 三个分析工具及其实时 input/output schema 校验；
- 通用 `tools/call`；
- 成功响应的任务级原子落盘、30分钟时效、连接/schema/完整性校验；
- 缓存时间水位输出。

脚本只直连 Streamable HTTP。当前连接为 SSE 时使用宿主原生 MCP 客户端，不要安装依赖或现场实现另一个 SSE 客户端。

## 平台选择

| 平台 | 启动器 | 解释器 |
|---|---|---|
| Windows | `scripts/report-mcp.ps1` | 系统 PowerShell 5.1 定位 `py -3` / `python` 后调用 Python 3.8+ |
| macOS | `scripts/report-mcp-macos.sh` | 系统 `/bin/sh` 定位 `python3` / `python` 后调用 Python 3.8+ |

两个启动器都只做解释器探测（版本 ≥3.8）与参数透传，不含业务逻辑；对同一套参数产生相同行为。Python 3.8+ 由用户或管理员预先安装（Windows 从 python.org，macOS 系统自带或经 Command Line Tools），除此之外不要在 Windows 上为此安装 WSL、Git Bash、Node.js、PowerShell 7 或任何 pip 包；不要在 macOS 上为此安装 Homebrew、jq 或任何 pip 包。

## 当前连接配置

执行任何脚本前，按 [连接准入与任务绑定](connection-and-clients.md#连接准入与任务绑定) 完成以下检查。**连接参数由脚本从宿主 MCP 配置中自动读取**，调用方不需要传地址、协议或 API-Key：

1. 脚本按固定顺序搜索宿主配置：环境变量 `YOYUYUN_MCP_CONFIG` / `MCP_CONFIG_PATH` → `~/.workbuddy/mcp.json` → `%APPDATA%/WorkBuddy/mcp.json` → `~/.codebuddy/mcp.json` → `~/.claude/mcp.json` → `~/.cursor/mcp.json` → `~/.config/mcp/mcp.json` → 当前目录 `.mcp.json` / `.workbuddy/mcp.json`。
2. 每个条目先按 `disabled` / `enabled` 过滤；`disabled: true` 或 `enabled: false` 一律排除，字段缺失不视为禁用，冲突时禁用优先。不得为检查连通性调用禁用连接。
3. 地址取自 `url`/`endpoint`/`serverUrl`；协议取自 `transport`/`type`/`protocol`（支持 `streamable-http` 及其别名；`sse` 明确拒绝并提示改用宿主原生工具）；凭据取自 `headers`，其次 `apiKey`/`api_key`/`token`，再次 `env` 中的 `X_API_KEY`/`API_KEY`/`MCP_API_KEY`；`${env:NAME}` 占位符在运行时展开。
4. 只有一个启用连接时直接使用；存在多个启用连接时，**优先按 SKILL.md「业务路由」通过 `--connection-name` 指定目标连接**（出租/租赁 → 悠租云；卖/销售 → 云掌柜）。未指定时脚本对最多 6 个候选各做一次握手，选中暴露三个分析工具的那个，并把探测结果写入 `transportWarnings` 同级的选择记录。这是**能力发现**，不是试错轮换：一旦绑定，本任务不再更换连接。注意多个连接可能都暴露三工具，能力发现无法区分业务系统，必须以业务路由为准。
5. 任务的连接名与指纹写入 `connection-binding.json`；后续调用命中绑定即直接复用，若指纹变化（地址或凭据变更）则停止并要求新任务。

`--connection-file` / `--connection-name` 仅在需要覆盖自动发现时传入。`--action connections` 可列出发现的配置文件与启用连接（只输出 Header 名称，不输出凭据）。

```json
{
  "mcpServers": {
    "report-analysis": {
      "transport": "streamable-http",
      "url": "<CURRENT_MCP_URL>",
      "headers": {
        "X-API-Key": "<CONFIGURED_OUTSIDE_CHAT>"
      }
    }
  }
}
```

配置含多个服务时无需再手工指定 `-ConnectionName`；脚本会自动识别。不要把密钥作为命令行参数、提示词或聊天内容传入；脚本不会把 Header 写入缓存或输出。

## 连接诊断（diagnose）

bootstrap 或首个 list 调用出现传输/握手失败后，需要区分故障层时，经用户同意用**新 taskId** 运行一次 diagnose。它复用预置脚本，不现场重写诊断客户端：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<SKILL_DIR>\scripts\report-mcp.ps1' `
  -Action diagnose `
  -TaskId '<NEW_DIAGNOSIS_UUID>' `
  -ConnectionFile '<CURRENT_CONNECTION_JSON>' `
  -ConnectionName 'report-analysis'
```

macOS：

```sh
sh '<SKILL_DIR>/scripts/report-mcp-macos.sh' \
  --action diagnose \
  --task-id '<NEW_DIAGNOSIS_UUID>' \
  --connection-file '<CURRENT_CONNECTION_JSON>' \
  --connection-name 'report-analysis'
```

诊断固定采样3组，每组 initialize → notifications/initialized → tools/list，最多9次HTTP请求，组间间隔2秒；不调用 tools/call、不读业务数据、不写业务缓存。单个请求不重试，带 session 的404允许继续采样；其他HTTP失败立即结束，网络/TLS失败停止。兼容开关不影响标准采样。

输出 steps.samples 和 steps.distribution，包含各方法状态计数、请求时间、会话指纹及协议版本。不输出凭据、session原文或错误堆栈。出现成功与失败混合时标为 intermittent-observed；全部样本一致只标为 sample-complete，不证明永久正常或确定性缺陷。提前结束标为 stopped-on-error。实际原因仍需管理员按指纹和时间对账。

## Windows 新任务启动

为每个用户任务生成新的随机 `taskId`，格式可使用 UUID。不得把历史任务的 ID 分配给新任务。先执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<SKILL_DIR>\scripts\report-mcp.ps1' `
  -Action bootstrap `
  -TaskId '<NEW_TASK_UUID>'
```

无需传 `-ConnectionFile`：脚本自动从宿主 MCP 配置发现地址、协议与凭据；多连接环境应按业务路由传 `-ConnectionName`。`bootstrap` 在线完成握手和 `tools/list`，随后调用 `yzy_list_report_analyses`，**stdout 输出紧凑目录摘要**（应用名、目录状态、报表编码/名称/示例问题）与 `liveToolSchemaHash`，**完整 schema 与结果落盘到 `fullOutputPath` 指向的文件**，并以 `catalog` 为键保存当前任务缓存。在线校验失败时停止，不能退回历史工具定义或旧连接。

macOS 使用系统 shell，无需赋予脚本可执行权限：

```sh
sh '<SKILL_DIR>/scripts/report-mcp-macos.sh' \
  --action bootstrap \
  --task-id '<NEW_TASK_UUID>'
```

## 会话404的有限恢复

只对 HTTP 404 且响应明确包含 `Session not found`、请求已携带 session 的情况启用以下内置恢复。它是对已观察到的**网关会话不粘滞**故障的有界处理，不是通用 MCP 会话恢复，也不证明服务端已修复。

- initialize 不重试；`tools/list` 和当前在线发现的三个只读 `tools/call`，每个请求最多尝试 **8 次**（首次加 7 次重试），间隔按 `1s × 尝试次数` 递增、上限 4s；保持 URL、凭据、session、协议版本、请求 ID 和参数不变。
- 同一 session 重试是**正确**的恢复方式：故障源于网关把同一 session 的请求路由到未持有该 session 的实例，重复发送最终会命中正确实例；换 session 或换连接都不能提高成功率。
- 实测参考（参考部署，10 次采样）：3 次重试累计成功率约 70%，5 次达 100%。旧版本固定 3 次重试是 `call` 动作频繁失败的直接原因。
- **重试参数是可用性保障，不得收紧**：8 次同 session 重试、退避 1s→上限 4s、单次调用 HTTP 请求总预算 32 属于脚本固定行为。即使服务端已修复粘滞路由、404 频率下降甚至消失，也不得以"服务已修好""重试用不上了"为由调低上限；下调必须经用户明确要求并单独确认。3 次重试只有约 70% 成功率的历史教训表明，收紧重试会把间歇性 404 变成直接查询失败。
- 每次脚本调用的 HTTP 请求总数上限为 **32**，跨 initialize、通知、tools/list 与 tools/call 共享；耗尽即停止并上报，不在脚本外继续重试。
- `initialized` 通知出现上述特定404时记录警告，继续在线 `tools/list`；不把任意非2xx都忽略，不根据一次结果断言通知不受支持。
- 普通404、400、401/403、5xx、网络超时、TLS错误及业务信封错误不适用该恢复。达到上限后停止并报告，不改路径、不切换连接、不自动新建 taskId。
- 成功后向用户披露 transportWarnings 中的重试与通知警告。未取得成功业务信封不得交付数据或写成功缓存。

## 调用当前工具

### 已确认服务缺陷的显式兼容模式

按失败方法区分兼容选项，不把某一部署的成功绕行推广为所有服务的默认行为。仅在用户或管理员已确认当前所选连接存在对应缺陷时，于任务首次调用前显式选择：

| 已确认缺陷 | Windows 参数 | macOS 参数 | 作用 |
|---|---|---|---|
| initialized 通知不被支持 | `-SkipInitializedNotification` | `--skip-initialized-notification` | 不发送该通知；tools/list 与 tools/call 保留 initialize 返回的 session |
| tools/list 携带 session 失败 | `-ToolsListWithoutSession` | `--tools-list-without-session` | 仅 tools/list 省略 session |

两个选项独立，不能因通知失败就启用无 session 模式；只有两个缺陷分别被确认才组合使用。默认仍发送 initialized 通知，不将 notifications 的所有错误一律忽略。跳过通知的模式仍必须在线 tools/list 并校验实时 schema，不可直接跳到 tools/call。后续调用沿用相同选项；脚本将其纳入任务绑定并输出启用状态。

已确认通知缺陷时的 Windows 启动示例：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<SKILL_DIR>\scripts\report-mcp.ps1' `
  -Action bootstrap -TaskId '<NEW_TASK_UUID>' `
  -ConnectionFile '<CURRENT_CONNECTION_JSON>' -ConnectionName '<SELECTED_ENABLED_CONNECTION>' `
  -SkipInitializedNotification
```

历史兼容模式不扩大下文有限恢复范围；超时不重试，连接准入及缓存规则不变。失败后不得自动改模式或重建 taskId；先报告并等待用户处置。

正常模式在 initialize 后使用服务端协商的协议版本头和 session。若用户或管理员已经确认所选启用连接存在“带 session 的 tools/list 失败，而同一 session 的 tools/call 正常”的服务缺陷，可在任务首次启动前显式选择 Windows 参数 `-ToolsListWithoutSession` 或 macOS 参数 `--tools-list-without-session`，后续步骤沿用同一模式。不得仅凭404自行开启；已有失败任务先停止并报告，用户明确处置后才建立新任务，不得自动换 taskId 重试。

无 session 选项仅对 tools/list 省略 session 头，仍使用同一 URL、凭据和协商协议版本在线获取 schema；未跳过的 initialized 通知和 tools/call 保留原始 session。这些选项属于已知非标准服务的兼容方式，不是通用协议行为，也不是免除在线发现的理由。兼容请求按下文有限恢复规则处理；不得轮换连接或改用历史 schema。

脚本在请求前输出所用连接及兼容模式；回答中须披露启用该模式的原因和范围。脚本在首次网络请求前保存任务连接绑定，禁止同一任务更改连接或兼容模式。配置中的禁用条目在请求前被拒绝。

### 调用参数

响应可为 JSON 或 SSE 帧；合并同一事件中的多行 data，按 JSON-RPC 请求 ID 匹配响应，不把尾随通知或最后一帧当作业务结果。工具结果优先读取 structuredContent，否则解析 content 中的文本 JSON；未获得有效业务信封时不能判为查询成功或写入成功缓存。

**输出格式（防截断误读）**：`bootstrap`、`call`、`read-cache` 的 stdout 只输出**紧凑摘要**（`summary`：状态、应用名、目录/报表/行数等业务要点）+ `liveToolSchemaHash` + `fullOutputPath`；完整业务信封与 liveTools schema 落盘在 `fullOutputPath` 文件中。**解析 columns、rows、报表编码、schema 等长内容时一律读取 `fullOutputPath` 文件，不要从终端 stdout 读取**——超长 stdout 会被终端折行截断，已发生过 reportCode 误读事故。会话404自动恢复成功的 transportWarnings 属已知基础设施现象，正常回答不需要转述给用户。

每次脚本进程都会重新连接并读取实时 schema，然后才校验参数并调用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<SKILL_DIR>\scripts\report-mcp.ps1' `
  -Action call `
  -TaskId '<SAME_TASK_UUID>' `
  -ToolName 'yzy_describe_report_analysis' `
  -ExpectedSchemaHash '<HASH_FROM_CURRENT_BOOTSTRAP>' `
  -ArgumentsFile '<PATH_TO_ARGS_JSON>'
```

macOS 等价调用：

```sh
sh '<SKILL_DIR>/scripts/report-mcp-macos.sh' \
  --action call \
  --task-id '<SAME_TASK_UUID>' \
  --tool-name 'yzy_describe_report_analysis' \
  --expected-schema-hash '<HASH_FROM_CURRENT_BOOTSTRAP>' \
  --arguments-file '<PATH_TO_ARGS_JSON>'
```

`--arguments-json` 也可直接传 JSON 字符串，但当参数里含引号、中文或嵌套对象时，多层 Shell/PowerShell 常改写引号导致解析失败；这种场景一律改用 `--arguments-file`，把 JSON 写入文件后传路径，避免转义问题。

`arguments` 元素六字段 `{name,label,kind,value,begin,end}` 均必填：`kind=single` 只填 `value`，`begin`/`end` 必须为空字符串（同时填会触发 `INVALID_ARGUMENT`）；`kind=range` 用 `begin`/`end`。

从 `fullOutputPath` 文件的 `liveTools[].inputSchema` 读取本次真实参数，并把 stdout 的 `liveToolSchemaHash` 传给后续 `call`。每次调用仍会在线发现工具；哈希变化时脚本拒绝调用，要求重新 bootstrap 并按新 schema 重建参数。脚本预置的工具名称是当前服务身份校验的一部分，不代表可以跳过在线发现。

不要把任一脚本包装在 `for`、`while`、轮询器、递归任务或自动重试队列中。先改成聚合查询或批量参数；确实无法合并时，也只有执行前能够证明总调用数为1–29次的固定有限循环才可作为例外，并且不得在运行时增加次数或拆批绕过限制。

## 缓存硬规则

- 缓存目录由 `taskId` 的 SHA-256 派生，清单内仍保存完整 `taskId` 并在读取时精确比对。
- 只缓存业务信封 `status=success` 的结果。有效期从成功响应写入数据文件并生成清单的 `persistedAtUtc` 开始计算。
- 默认有效期固定为30分钟，不能通过参数放宽。
- 读取缓存前仍重新连接当前 MCP 并执行 `tools/list`。连接指纹（URL 与 Header 值只做 SHA-256，不落盘明文）、实时工具 schema 哈希、任务 ID 或文件摘要任一不匹配即拒绝。
- 缓存只属于创建它的任务，禁止跨任务读取、复制、改名复用或通过传入旧 `taskId` 冒充当前任务。
- 超过30分钟默认拒绝。只有用户明确要求使用过期数据时，才可对当前任务增加 `-AllowExpiredCache`；该参数不能解除任务隔离、连接校验或 schema 校验。

读取当前任务缓存：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<SKILL_DIR>\scripts\report-mcp.ps1' `
  -Action read-cache `
  -TaskId '<SAME_TASK_UUID>' `
  -ConnectionFile '<CURRENT_CONNECTION_JSON>' `
  -ConnectionName 'report-analysis' `
  -CacheKey 'catalog'
```

macOS：

```sh
sh '<SKILL_DIR>/scripts/report-mcp-macos.sh' \
  --action read-cache \
  --task-id '<SAME_TASK_UUID>' \
  --connection-file '<CURRENT_CONNECTION_JSON>' \
  --connection-name 'report-analysis' \
  --cache-key 'catalog'
```

`cache` 对象会返回 `fetchedAtUtc`、`persistedAtUtc`、`expiresAtUtc`、`ageMinutes`、`ttlMinutes` 和 `stale`。使用缓存回答时向用户用一行通俗话报告等效信息（数据获取时间、缓存是否在 30 分钟有效期内、是否已过期），不罗列技术字段名；仅检查缓存但最终使用在线结果时无需声称使用了缓存。`read-cache` 的 stdout 同样是紧凑摘要 + `fullOutputPath`，完整缓存内容从落盘文件读取。

## 本地缓存范围

默认缓存根目录是系统临时目录下的 `yozuyun-analysis-skill-cache`。可以用 `-CacheRoot` 指向当前任务允许写入的位置，但不要指向共享交付目录、版本库或其他任务目录。缓存只用于当前任务的短期复用，不作为报表归档、跨会话知识或后续任务的数据源。
