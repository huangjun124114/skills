# MCP 工具契约速查

本文用于理解业务语义，不是可直接重放的工具 schema。每个新会话都必须从当前有效 MCP 的 `tools/list` 读取实际 input/output schema；发生差异时以当前在线定义为调用依据，并停止使用旧参数或缓存定义。

## 统一信封

三个工具都返回同一结构，MCP 2.0 同时提供等价的文本 `content` 与 `structuredContent`：

```json
{
  "status": "success|error",
  "data": {},
  "meta": {},
  "warnings": [],
  "error": null
}
```

优先读取 `structuredContent`。成功时使用 `data`；失败时使用 `error.code/stage/retryable/action`。保留 `meta.requestId` 供排障，不向用户暴露内部 SQL、堆栈或凭据。

常用元数据：

- `contractVersion`：外部契约版本，当前为 `2.0`。
- `serverVersion`：服务版本。
- `analysisDefinitionVersion`：本次定义版本。
- `metricCatalogVersion`：指标目录摘要版本。
- `logicalSchemaVersion`：逻辑 Schema 版本。
- `queriedAt`：服务端查询时间。
- `catalogState`：仅 list 使用的目录状态。
- `scope.effectiveArguments`：analyze 实际生效的业务参数。
- `truncated`：是否截断；受控分析超限通常直接拒绝。

## yzy_list_report_analyses

无输入。`data` 始终为当前用户可分析报表数组。关键字段：

- `reportCode`：后续 describe/analyze 的报表编码。
- `name`、`purpose`、`sampleQuestions`：选表依据。
- `logicalTable`、`grain`、`statDimensions`：粒度与维度能力提示。
- `metricCodes`、`metricCatalogVersion`：指标覆盖提示。
- `analysisDefinitionVersion`：目录中的定义版本提示；执行前仍需 describe。
- `databaseType`、`databaseVersion`：SQL 方言提示。

空数组必须结合 `meta.catalogState` 解释：`READY`、`NO_AUTHORIZED_REPORTS`、`NO_READY_REPORTS`。

## yzy_describe_report_analysis

输入：`reportCode`，必须来自 list。

关键输出：

- `logicalTable`：唯一 FROM 目标。
- `columns[]`：字段名、标签、类型、单位、字典、权限位、敏感标记和指标映射。
- `parameters[]`：业务参数的类型、输入形态、是否必填、默认值、字典和通道。
- `dictionaries`：展示值与编码映射。
- `metrics[]`：`id/code/name/caliber/unit/sourceColumns/definitionVersion`。空字段表示主数据没有可靠来源，不得推断。
- `sqlSubset`：允许的语句、子句、聚合、禁止形态和绑定风格。
- `limits`：结果行数、绑定数量、SQL 字节和超时硬限额。
- `analysisDefinitionVersion`：analyze 必填版本。

列权限语义：

- `selectable`：可投影。
- `filterable`：可过滤。
- `groupable`：可分组。
- `aggregatable`：可聚合。
- `allowedAggregates`：该列允许的聚合函数。
- `sensitive`：可按策略过滤，但不可输出、排序、分组或聚合。

## yzy_analyze_report

输入：

- `reportCode`：选定报表编码。
- `analysisSql`：符合 describe 的单表 SELECT，命名绑定使用 `:name`。
- `arguments`：可选业务参数数组，元素为 `{name,label,kind,value,begin,end}`。
- `bindings`：可选 SQL 绑定对象，值为 `{value,type}`；type 仅为 `STRING/LONG/DECIMAL/DATE/DATETIME/BOOLEAN`。
- `maxResultRows`：可选，实际限制不超过服务端硬上限。
- `analysisDefinitionVersion`：必填，必须与本次 describe 一致。

结果 `data`：

- `columns[]`：结果列名和类型，可包含 `sourceColumn/label/unit/metricCode/dicCode`。
- `rows[]`：每行是与 columns 同序的值数组。
- `returnedRows`、`resultLimited`：返回规模。
- `effectiveArguments`：实际业务参数。
- `analysisDefinitionVersion`：执行所用版本。
- `warnings`、`queriedAtIso`、`requestId`：告警、时间和追踪信息。

`COUNT(*)` 等没有单一来源列的结果，其语义字段可能为 null。不要按别名补造标签、单位或指标编码。


## 业务应用身份

`meta.application` 为可空的 `{code, displayName}`，来自当前 report 宿主配置，仅用于展示。旧版 report 未提供时为 null，查询仍正常。优先使用本次返回的 displayName；缺失使用“当前业务系统”。既有 systemId/sourceReference 是兼容技术标识，不代表品牌，也不是授权或路由依据。
