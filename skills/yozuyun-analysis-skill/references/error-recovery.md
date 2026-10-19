# 错误与恢复

取得有效业务 JSON 信封后，优先执行 `error.action`。同一错误未经输入或外部状态变化，不要连续重试。错误恢复不得放入循环或持续轮询；表中允许的“重试一次”就是该错误的完整重试预算。业务恢复也只在已绑定连接内执行，不授权切换连接。

## 传输层与握手阶段失败

本节与业务 `error.code` 表并列。尚未取得有效 JSON 信封时适用本节，不套用业务表中的重试次数。以下均为必须向用户报告的故障，不是换连接重试的理由：

| 现象 | 必须执行的处置 |
|---|---|
| HTTP 404 | 仅符合 [会话404有限恢复](runtime-and-cache.md#会话404的有限恢复) 时按预置预算恢复；其他情况或预算耗尽立即停止并报告，不切换连接 |
| HTTP 401/403 | 停止，报告连接名称及实际状态码，请用户在客户端核对凭据或权限；不索要密钥原文，不换连接重试 |
| 连接超时 | 停止，报告连接名称、超时阶段及已知时限，请用户检查网络或服务；不得自动重试或换连接 |
| 连接被拒 | 停止，报告连接名称和拒绝连接现象，请用户检查服务监听与网络；不得换连接重试 |
| HTTP 5xx | 停止，报告连接名称及实际状态码，请用户或管理员检查服务与网关；不得套用业务 RETRY 或换连接重试 |
| TLS/证书错误 | 停止，报告连接名称和证书校验失败现象，请用户检查证书与信任配置；不得关闭证书校验、降级协议或换连接 |

其他握手失败、非预期内容或无法解析的响应同样停止并报告。仅陈述已观察到的现象，将原因表述为待核实；没有 HTTP 状态码时说明未取得，不编造状态码或 requestId。不输出密钥、内部地址、上游原文或堆栈。等待用户处置，不用历史连接或缓存掩盖故障。

通知失败不等于通知不受支持。明确的 Session not found 404 按有限恢复规则记录警告并继续；其他错误停止。diagnose 用固定三组采样记录分布，不把单次通知失败、tools/list 成功判成 notification-only-defect。不得用兼容开关猜测根因。

## 业务信封错误

| error.code | action | Skill 行为 |
|---|---|---|
| `INVALID_ARGUMENT` | `FIX_INPUT` | 核对工具必填项、参数结构、类型和版本 |
| `INVALID_FILTER` | `FIX_INPUT` | 对照 describe 的字段、字典和参数规则修正筛选 |
| `NEEDS_CLARIFICATION` | `ASK_USER` | 一次询问缺失或歧义的必要信息 |
| `UNAUTHENTICATED` | `UPDATE_CONNECTION_CREDENTIAL` | 指导用户在连接 Header 更新 `X-API-Key`，不要索要密钥原文 |
| `FORBIDDEN` | `CHECK_PERMISSION` | 说明当前身份无权限，建议管理员检查报表授权 |
| `CAPABILITY_DISABLED` | `SELECT_AVAILABLE_REPORT` | 重新 list；若仍不可用，联系管理员启用能力 |
| `REPORT_NOT_ANALYZABLE` | `SELECT_AVAILABLE_REPORT` | 重新 list 选择 READY 报表，不绕过发布状态 |
| `REPORT_DEFINITION_CHANGED` | `REDESCRIBE` | 重新 describe，重建 SQL 与参数后只重试一次 |
| `ANALYSIS_SQL_REJECTED` | `REBUILD_QUERY` | 对照 columns/sqlSubset/limits 重建更简单的查询 |
| `RESULT_LIMIT_EXCEEDED` | `NARROW_QUERY` | 增加必要筛选、聚合或缩小时间范围；需要业务取舍时询问用户 |
| `RATE_LIMITED` | `RETRY_LATER` | 告知用户稍后重试，不高频循环调用 |
| `UPSTREAM_TIMEOUT` | `RETRY` | 原样重试至多一次；再次失败时返回 requestId 和建议 |
| `UPSTREAM_UNAVAILABLE` | `RETRY` | 原样重试至多一次；再次失败时说明服务暂不可用 |
| `OUTPUT_REJECTED` | `CONTACT_ADMIN` | 停止重试，提供 requestId 请管理员排查 |

## 目录为空

list 成功且 `data=[]` 不属于工具失败：

- `NO_AUTHORIZED_REPORTS`：用户没有授权报表。建议管理员分配权限。
- `NO_READY_REPORTS`：用户有报表权限，但没有 READY、未漂移且已开放的分析定义。建议管理员开放或重新发布。
- `READY` 与空数组同时出现：视为契约异常，使用 requestId 联系管理员。

## 安全表达

- 对用户显示安全错误说明、下一步和 requestId。
- 不输出上游原文、SQL、绑定值、堆栈、内部地址、Cookie 或凭据。
- 若修复需要用户改变业务范围，说明影响后再询问；不要静默修改条件。
