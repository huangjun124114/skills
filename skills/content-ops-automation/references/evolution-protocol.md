# 自进化协议

> 版本：1.0 | 最后更新：2026-07-31

## 设计理念

本框架的核心创新是**自进化能力**——通过分析效果数据，自动优化自身模板和策略，实现"越用越好"。

进化遵循以下原则：
1. **数据驱动**：所有优化基于实际效果数据，而非主观判断
2. **渐进式**：从小范围调整开始，验证有效后再扩大
3. **可追溯**：每次变更都记录原因和结果
4. **安全边界**：核心架构不可变，只有模板和策略可优化

## 进化触发点

| 触发条件 | 进化级别 | 执行动作 |
|---------|---------|---------|
| 每次流水线完成 | 记录 | 追加效果数据到 evolution-log |
| 每发布 5 篇 | 微进化 | 优化当前最有效的专家模板 |
| 每发布 10 篇 | 中进化 | 审视选题策略 + 排期规则 |
| 每发布 30 篇 | 大进化 | 全面审视架构、专家池、调度规则 |

## 进化流程

### Step 1: 数据采集

```python
def collect_performance_data(n_recent: int = 10):
    """采集最近 N 条流水线的效果数据"""
    registry = read_registry()
    completed = [p for p in registry["completed"] if p.get("performance")]
    
    data = []
    for pipeline in completed[-n_recent:]:
        perf = read_performance_file(pipeline["id"])
        data.append({
            "pipeline_id": pipeline["id"],
            "content_type": pipeline["type"],
            "expert": pipeline["expert"],
            "publish_time": pipeline["completed_at"],
            "views": perf["total_views"],
            "engagement_rate": perf["engagement_rate"],
            "conversion_rate": perf["conversion_rate"],
            "hours_spent": calculate_total_hours(pipeline["id"])
        })
    
    return data
```

### Step 2: 模式识别

```python
def analyze_patterns(data: list) -> dict:
    """分析效果数据中的模式"""
    
    # 1. 按专家类型分组
    by_expert = {}
    for item in data:
        expert = item["expert"]
        if expert not in by_expert:
            by_expert[expert] = []
        by_expert[expert].append(item)
    
    # 2. 计算每个专家的平均效果
    expert_stats = {}
    for expert, items in by_expert.items():
        avg_views = sum(i["views"] for i in items) / len(items)
        avg_engagement = sum(i["engagement_rate"] for i in items) / len(items)
        expert_stats[expert] = {
            "count": len(items),
            "avg_views": avg_views,
            "avg_engagement": avg_engagement,
            "best_article": max(items, key=lambda x: x["views"])
        }
    
    # 3. 识别最佳专家
    best_expert = max(expert_stats, key=lambda k: expert_stats[k]["avg_views"])
    
    # 4. 按内容类型分组
    by_type = {}
    for item in data:
        ctype = item["content_type"]
        if ctype not in by_type:
            by_type[ctype] = []
        by_type[ctype].append(item)
    
    # 5. 识别最佳内容类型
    type_stats = {}
    for ctype, items in by_type.items():
        avg_views = sum(i["views"] for i in items) / len(items)
        type_stats[ctype] = {
            "count": len(items),
            "avg_views": avg_views
        }
    best_type = max(type_stats, key=lambda k: type_stats[k]["avg_views"])
    
    return {
        "best_expert": best_expert,
        "expert_stats": expert_stats,
        "best_type": best_type,
        "type_stats": type_stats
    }
```

### Step 3: 模板更新

根据模式识别结果，更新对应的 Skill 文件：

```python
def update_expert_skill(expert: str, patterns: dict):
    """更新专家 Skill 文件"""
    
    # 1. 读取当前 Skill 文件
    skill_file = f"skills/{expert}.md"
    content = read_file(skill_file)
    
    # 2. 提取最佳文章的成功经验
    best_article = patterns["expert_stats"][expert]["best_article"]
    success_patterns = extract_success_patterns(best_article)
    
    # 3. 更新 Skill 文件
    # - 在"历史案例库"中新增案例
    # - 在"写作模板"中补充成功模式
    # - 在"迭代记录"中记录本次更新
    
    updated_content = update_skill_content(content, success_patterns)
    
    # 4. 写入文件
    write_file(skill_file, updated_content)
    
    # 5. 更新版本号
    increment_version(skill_file)
```

### Step 4: 日志记录

每次进化都记录到 `evolution-log.md`：

```markdown
# 进化日志

## 2026-08-15 v1.1 微进化

**触发条件**：发布 5 篇文章
**分析范围**：PL-20260731-001 至 PL-20260810-001（共 5 篇）

**发现模式**：
- 📋 政策解读者平均阅读量 2,100（最佳）
- 💡 痛点猎手平均阅读量 1,200（待优化）
- 政策解读类内容点击率最高（35%）

**执行优化**：
1. 更新 policy-writer.md：
   - 新增"产品植入"段落过渡技巧
   - 补充"数据引用必须标注出处"规则
2. 更新 painpoint-writer.md：
   - 优化开头故事构建方式
   - 增加共情触发点设计

**预期效果**：痛点类文章阅读量提升 30%

---

## 2026-07-31 v1.0 初始化

- 创建 5 个专家 Skill 文件
- 配置三层调度架构
- 启动第一条流水线
```

### Step 5: 通知用户

进化完成后，向用户推送报告：

```
🔄 Skill 已进化（v1.0 → v1.1）

分析范围：最近 5 篇文章
最佳专家：📋 政策解读者（平均阅读量 2,100）
最佳类型：政策解读（点击率 35%）

优化内容：
1. policy-writer.md：新增产品植入过渡技巧
2. painpoint-writer.md：优化开头故事构建

预期效果：痛点类文章阅读量提升 30%
```

## 进化边界

### 可自动更新（无需用户确认）

| 范围 | 说明 |
|------|------|
| 专家模板写作规则 | 标题公式、结构模板、段落过渡 |
| 选题策略权重 | 素材质量评分、时效性评分 |
| 排期规则 | 内容类型分布、热点响应策略 |
| 通知模板 | 措辞、格式、emoji 使用 |
| 配图建议 | 封面图风格、配图密度 |
| 质量检查清单 | 新增/删除检查项 |

### 需用户确认（推送通知等待审批）

| 范围 | 说明 |
|------|------|
| 新增/删除专家角色 | 需要修改专家池结构 |
| 修改调度频率 | L0/L1 的触发间隔 |
| 修改归档策略 | 保留天数、归档触发条件 |
| 修改配置参数 | 自动确认时间、休息日等 |

### 不可更新（核心架构）

| 范围 | 说明 |
|------|------|
| 三层调度架构 | L0/L1/L2 结构 |
| 状态机定义 | 12 个阶段的状态流转 |
| 流水线规范 | 文件结构、命名规则 |
| Skill 核心信息 | name、description |

## 效果数据采集规范

### 采集时间点

| 时间点 | 采集内容 | 备注 |
|--------|---------|------|
| 发布后 24h | 阅读量、点赞、评论、转发 | 初步效果 |
| 发布后 48h | 同上 | 稳定期 |
| 发布后 7d | 同上 + 留资线索 | 最终数据 |

### 数据来源

**MVP 阶段（0-3 月）**：手动录入
- 用户每日在 `performance.md` 中填写各平台数据
- L1 调度器自动计算汇总指标

**半自动阶段（3-6 月）**：API 采集
- 接入公众号/知乎/头条 API
- 自动获取阅读量、互动数据

**全自动阶段（6 月+）**：爬虫 + API
- 定时任务自动采集所有平台数据
- 无需人工干预

### 效果评级

```python
def calculate_rating(views: int, historical_avg: int) -> str:
    """根据阅读量评级"""
    ratio = views / historical_avg
    
    if ratio >= 2.0:
        return "⭐⭐⭐⭐⭐ 卓越"
    elif ratio >= 1.5:
        return "⭐⭐⭐⭐ 优秀"
    elif ratio >= 1.0:
        return "⭐⭐⭐ 达标"
    elif ratio >= 0.5:
        return "⭐⭐ 待优化"
    else:
        return "⭐ 需改进"
```

## 进化触发检查点

在 L1 调度器中增加进化检查：

```python
def check_evolution_trigger():
    """检查是否触发进化"""
    registry = read_registry()
    completed_count = len(registry["completed"])
    
    # 每 5 篇触发微进化
    if completed_count % 5 == 0 and completed_count > 0:
        trigger_micro_evolution()
    
    # 每 10 篇触发中进化
    if completed_count % 10 == 0 and completed_count > 0:
        trigger_meso_evolution()
    
    # 每 30 篇触发大进化
    if completed_count % 30 == 0 and completed_count > 0:
        trigger_macro_evolution()
```

## 进化安全措施

1. **版本控制**：每次更新都递增版本号，保留历史版本
2. **回滚机制**：如果进化后效果下降，可回滚到上一版本
3. **用户确认**：重大变更需用户审批
4. **渐进式**：从小范围调整开始，验证有效后再扩大

## 进化日志维护

`evolution-log.md` 文件结构：

```markdown
# 进化日志

## <日期> v<版本号> <进化级别>

**触发条件**：<触发条件>
**分析范围**：<分析的流水线范围>

**发现模式**：
- <模式 1>
- <模式 2>

**执行优化**：
1. <优化 1>
2. <优化 2>

**预期效果**：<预期改进>

---

（按时间倒序排列）
```
