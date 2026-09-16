# 调度规则与动态排期策略

> 版本：1.0 | 最后更新：2026-07-31

## 调度参数

| 参数 | 默认值 | 说明 | 可配置 |
|------|--------|------|--------|
| L0 触发时间 | 工作日 08:00 | 每日写作计划创建时间 | ✅ |
| L1 扫描间隔 | 每小时 1 次 | 流水线状态推进频率 | ✅ |
| 选题自动确认时间 | 5 分钟 | 用户未干预时的自动确认时间 | ✅ |
| 流水线归档天数 | 30 天 | 已完成流水线保留天数 | ✅ |
| 休息日 | 周日 | 不创建流水线的日期 | ✅ |

## 内容排期策略

### 默认排期

| 星期 | 内容类型 | 匹配专家 | 备注 |
|------|---------|---------|------|
| 周一 | 政策解读 | 📋 政策解读者 | 周末政策汇总 |
| 周二 | 行业观察 | 📰 行业观察家 | 行业动态跟踪 |
| 周三 | 产品功能 | 🚀 产品布道师 | 产品更新发布 |
| 周四 | 痛点场景 | 💡 痛点猎手 | 客户故事挖掘 |
| 周五 | 行业月报 | 📰 行业观察家 | 本周行业汇总 |
| 周六 | 休息 | - | 不创建流水线 |
| 周日 | 休息 | - | 不创建流水线 |

### 动态排期调整逻辑

排期作为"默认建议"，L0 调度器可根据以下规则动态调整：

```python
def dynamic_adjust_type(default_type: str) -> tuple:
    """
    根据素材质量/热点/历史分布动态调整内容类型。
    返回 (最终类型, 调整原因)。
    """
    
    # 规则 1：热点事件优先（最高优先级）
    hot_events = scan_hot_events(today_briefs)
    if hot_events:
        hot_type = match_type_to_event(hot_events[0])
        return (hot_type, f"热点事件：{hot_events[0]['title']}")
    
    # 规则 2：素材质量驱动
    material_quality = assess_material_quality(today_briefs)
    if material_quality["best_type"] and material_quality["best_count"] >= 5:
        return (material_quality["best_type"],
                f"今日{material_quality['best_type']}素材丰富（{material_quality['best_count']}条）")
    
    # 规则 3：历史分布均衡
    recent_dist = get_recent_type_distribution(days=7)
    if recent_dist[default_type] >= 3:
        min_type = min(recent_dist, key=recent_dist.get)
        return (min_type, f"近 7 天{default_type}已使用{recent_dist[default_type]}次，切换至{min_type}")
    
    # 无触发条件，使用默认排期
    return (default_type, None)
```

### 动态排期优先级

| 优先级 | 触发条件 | 行为 |
|--------|---------|------|
| 1（最高） | 今日素材含热点事件 | 直接匹配热点对应类型 |
| 2 | 某类素材特别丰富（≥5 条） | 优先使用素材最丰富的类型 |
| 3 | 默认类型近 7 天已用 ≥3 次 | 切换至使用最少的类型 |
| 4（默认） | 以上均不触发 | 使用星期排期默认建议 |

### 调整通知规则

当排期发生调整时，通知中**必须标注调整原因**：

```
⚠️ 排期调整：[原类型] → [新类型]（原因：[具体原因]）
```

用户可在 5 分钟内回复修改选题。

## 选题推荐规则

### 选题候选生成

L0 调度器在创建流水线时，生成 5 个选题候选：

```python
def generate_topic_candidates(briefs, content_type):
    """根据素材和内容类型生成选题候选"""
    candidates = []
    
    for brief in briefs:
        # 1. 评估素材质量
        quality_score = assess_brief_quality(brief)
        
        # 2. 评估与内容类型的匹配度
        match_score = assess_type_match(brief, content_type)
        
        # 3. 评估时效性
        freshness_score = assess_freshness(brief)
        
        # 4. 综合评分
        total_score = quality_score * 0.4 + match_score * 0.4 + freshness_score * 0.2
        
        if total_score >= 0.6:  # 阈值
            candidates.append({
                "title": generate_topic_title(brief),
                "brief": brief,
                "score": total_score,
                "type": content_type
            })
    
    # 按评分排序，取前 5
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:5]
```

### 选题去重

```python
def select_best_topic(candidates, recent_topics):
    """从候选中选择最佳选题，避免与近期主题重复"""
    for candidate in candidates:
        # 检查是否与近期主题重复
        is_duplicate = False
        for recent in recent_topics:
            if similarity(candidate["title"], recent["title"]) > 0.7:
                is_duplicate = True
                break
        
        if not is_duplicate:
            return candidate
    
    # 如果所有候选都重复，返回评分最高的
    return candidates[0] if candidates else None
```

## 通知规则

### 通知时机

| 时机 | 通知内容 | 接收人 |
|------|---------|--------|
| L0 创建流水线 | 今日写作任务安排 | 运营负责人 |
| 选题自动确认 | 选题已自动确认 | 运营负责人 |
| 终稿就绪 | 请审批 | 审批人 |
| 审批通过 | 文章已发布 | 运营负责人 |
| 周度复盘 | 上周运营数据 | 运营负责人 |

### 通知模板

```
📝 今日写作任务已安排

流水线：PL-20260801-001
选题：厦门"5 折租房"政策升级
类型：政策解读
专家：📋 政策解读者
预计完成：10:00

如需调整，请在 5 分钟内回复"修改选题"
```

```
📝 终稿已就绪，请审批

流水线：PL-20260801-001
标题：厦门"5 折租房"政策升级，人才公寓运营方如何接招？
字数：1,680 字
创作专家：📋 政策解读者
润色专家：🔍 内容打磨师

请回复"通过"或修改意见
```

## 特殊日期处理

| 日期类型 | 处理方式 |
|---------|---------|
| 法定节假日 | 不创建流水线（可手动触发） |
| 重大政策发布日 | 立即手动触发热点流水线 |
| 产品发布日 | 提前 1 天手动创建产品类流水线 |
