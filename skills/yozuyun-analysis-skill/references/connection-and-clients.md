# 连接与客户端适配

## 连接准入与任务绑定

1. 在连接或调用前本地枚举当前宿主的配置条目，先检查每个条目的 `disabled` / `enabled`；枚举不发送网络请求、不输出 Header 或凭据。`disabled: true` 或 `enabled: false` 均视为禁用，用户明确禁用的连接也排除；字段缺失不视为禁用，冲突时禁用优先。字段值无法判定时停止并请用户核对，不猜测启用状态。存在 X-API-Key、密钥未过期或技术标识相同都不是启用依据。
2. 排除禁用条目，不对它们执行握手或业务调用。即使能够连通、返回完整数据，也不得使用。没有启用连接时停止并请用户配置。
3. 脚本自动从配置读取连接参数：地址取 `url`/`endpoint`/`serverUrl`，协议取 `transport`/`type`/`protocol`，凭据取 `headers`，其次 `apiKey`/`api_key`/`token`，再次 `env` 的 `X_API_KEY`/`API_KEY`/`MCP_API_KEY`。调用方不需要、也不应该手工传这些值。
4. 只有一个启用连接时直接绑定；存在多个启用连接时，脚本对最多 6 个候选各做一次 `initialize + tools/list`，选中唯一暴露三个分析工具的那个。这是按能力识别数据源的一次性发现，与"试错式轮换"有本质区别：发现过程有固定上限、只读握手、不取业务数据，且选中后本任务不再更换连接。
5. 选定连接与指纹写入任务绑定文件，后续步骤直接复用；指纹变化（地址或凭据变更）时停止并要求用户开新任务。连接名称不能替代响应中的业务应用身份。
6. 禁止在绑定后试错式轮换连接。选定连接失败时仅允许预置的会话404有限恢复，除此之外按 [传输层与握手阶段失败](error-recovery.md#传输层与握手阶段失败) 停止并报告，不尝试配置中的其他连接，不自行修改 URL、协议或启用状态。需要改换连接时，由用户处置并明确新任务，再重新准入和绑定；不得通过新建 taskId 自行规避。

以上规则同时适用于宿主原生工具和预置脚本 fallback；工具可见或服务可达不等于用户已启用该连接。

## 判断连接状态

只使用所选配置的 URL 本体，不删改路径、不追加后缀、不探测备用路径。宿主权限拒绝与服务端 HTTP 错误分开记录；权限拒绝不证明服务返回了403，不得换工具或路径绕过拒绝。

按以下顺序判断，不要仅凭用户说“已经配置”就视为连接成功：

1. 在每个新会话中，从当前智能体有效连接重新发现工具；不能沿用历史会话、旧连接或缓存的工具列表和参数。
2. 工具列表中能否看到且仅看到 `yzy_list_report_analyses`、`yzy_describe_report_analysis`、`yzy_analyze_report`，并读取实时 input/output schema。
3. 调用 `yzy_list_report_analyses` 是否得到统一 JSON 信封。
4. 信封为失败时，读取 `error.code`、`error.action` 和 `meta.requestId`；不要要求用户提供密钥原文。
5. list 成功但 `data=[]` 时，读取 `meta.catalogState`，按目录状态解释。

宿主不能直接调用工具但有当前连接配置时，Windows 使用 Skill 预置的 `scripts/report-mcp.ps1`，macOS 使用 `scripts/report-mcp-macos.sh` 完成上述检查；连接配置由脚本自动发现，无需手工传入。详细方式见 [runtime-and-cache.md](runtime-and-cache.md)。

## 应用身份核对

list 成功后读取本次信封的 `meta.application.displayName`，向用户说明连接名称与实际应用名称。连接名称仅用于配置选择，不能证明业务系统身份；相同工具名、服务版本或 systemId 不代表同一业务应用。

用户指定了业务系统但响应身份不匹配或缺失时，停止在 describe/analyze 之前，报告差异并请用户核对；不改换连接验证猜测。用户未指定业务系统且身份缺失时，沿用“当前业务系统”，不补造品牌。后续响应身份发生变化时，同样停止并报告。

每个应用的报表目录、字段口径、日期语义、SQL 方言及定义版本均取自本任务实时 list/describe，不共享其他应用的历史经验。失败时不交付文档中的历史报表清单作为当前可用目录；mock 标志仅按服务返回说明，不据此推断租户身份或数据完整性。

## 推荐连接配置

生产地址、路径和 API-Key 由业务系统管理员提供。示例中的值都是占位符：

```json
{
  "name": "report-analysis",
  "transport": "streamable-http",
  "url": "<MCP_SERVER_BASE_URL>/mcp",
  "headers": {
    "X-API-Key": "<YOUR_API_KEY>"
  }
}
```

兼容客户端不支持 Streamable HTTP 时使用 SSE：

```json
{
  "name": "report-analysis",
  "transport": "sse",
  "url": "<MCP_SERVER_BASE_URL>/sse",
  "headers": {
    "X-API-Key": "<YOUR_API_KEY>"
  }
}
```

服务端消息路径默认为 `/mcp/message`。仅当客户端要求单独填写 SSE 消息地址时配置它。

## 配置原则

- 配置阶段首选 Streamable HTTP `/mcp`；客户端不支持时由用户配置 SSE `/sse`。任务中的连接失败不得触发自动回退协议或切换端点。
- API-Key 只放在连接 Header `X-API-Key`，不放 URL、查询参数、提示词、聊天消息或 Skill 文件。
- 客户端若提供 Header JSON 输入框，只填写类似 `{"X-API-Key":"<YOUR_API_KEY>"}` 的对象。
- 客户端若分别提供名称、地址、协议和 Header 表单，逐项填写同一信息。
- 保存后刷新工具列表，并用 list 工具做最小探测。
- 新会话重新刷新工具列表和参数；发现 schema 变化后重建参数，不能重放旧请求。
- 不把 API-Key 转换成用户 ID、租户 ID 或其他模型参数；身份完全由服务端建立。

## WorkBuddy、千问 Work 与豆包工作

桌面宿主的版本和入口名称可能变化，因此按能力配置，不臆造固定菜单路径：

1. 找到“自定义 MCP / MCP 服务器 / 工具连接”入口。
2. 优先选择 Streamable HTTP；若宿主仅支持 SSE，则使用兼容地址。
3. 填写服务器 URL，在 Header 配置中填 `X-API-Key`。
4. 连接后确认三个工具均可见，再运行 list 探测。
5. 若宿主只显示文本结果，继续使用；Skill 从 `content` 中解析统一 JSON。
6. 若宿主支持 `structuredContent` 和 output schema，优先按结构化对象读取，避免二次解析数字。
7. 若宿主支持 HTML 文件预览或工件，报告模式输出 HTML；支持打印或导出时再生成 PDF。

## 常见连接结果

| 现象 | 解释 | 处理 |
|---|---|---|
| 三工具均不可见 | 服务器未连接、协议/地址错误或宿主未刷新 | 核对协议、URL，重新连接并刷新工具 |
| `UNAUTHENTICATED` | Header 缺失、API-Key 无效或下游会话失效 | 在客户端更新 `X-API-Key`，再调用 list |
| `FORBIDDEN` | 已认证但无相应权限 | 联系管理员核对业务系统报表权限 |
| list 成功，`NO_AUTHORIZED_REPORTS` | 当前用户没有授权报表 | 联系管理员分配报表权限 |
| list 成功，`NO_READY_REPORTS` | 有报表权限，但无 READY 且未漂移的分析定义 | 联系管理员开放或重新发布报表分析定义 |
| 仅 SSE 失败 | 客户端或网关的 SSE 配置可能不匹配 | 停止并报告，请用户核对当前连接与网关；不得自行尝试其他协议或连接 |

