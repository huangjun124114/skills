# 三层调度架构规范

> 版本：1.0 | 最后更新：2026-07-31

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    L0 · 每日写作计划调度器                            │
│                    频率：工作日 08:00 + 手动触发                      │
│                                                                     │
│  职责：                                                             │
│  • 读取「内容排期策略」确定今日内容类型（默认建议）                    │
│  • 动态调整：扫描素材质量/热点事件/历史分布，可覆盖默认排期            │
│  • 扫描素材库，挑选最佳题材                                          │
│  • 创建今日流水线实例                                                │
│  • 分配内容类型 + 匹配专家                                           │
│  • 推送通知（含 5 分钟确认提示）                                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    L1 · 流水线调度器                                  │
│                    频率：每小时 1 次                                   │
│                                                                     │
│  职责：                                                             │
│  • 扫描所有活跃流水线                                                │
│  • 按状态机规则推进每个流水线的阶段                                  │
│  • 调用对应专家 Skill 执行创作/润色                                  │
│  • 更新状态文件 + 重新生成仪表盘                                     │
│  • 触发通知                                                        │
│  • 检查过期流水线并执行归档                                          │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    L2 · 固定专家池（执行层）                          │
│                                                                     │
│  📋 政策解读者    📰 行业观察家    🚀 产品布道师                      │
│  (policy-writer)  (industry-writer) (product-writer)                │
│                                                                     │
│  💡 痛点猎手      🔍 内容打磨师                                      │
│  (painpoint-writer) (polisher)                                      │
│                                                                     │
│  每个专家拥有：独立 Skill 文件（持续迭代） + 历史案例库               │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心组件说明

| 组件 | 类型 | 职责 |
|-----|------|------|
| L0 每日写作计划调度器 | WorkBuddy Automation | 每日自动布置写作任务（含动态排期） |
| L1 流水线调度器 | WorkBuddy Automation | 每小时推进流水线状态 |
| 固定专家池 | Skill 文件 | 5 类专家角色，持续迭代优化 |
| 流水线状态管理 | Markdown 文件 | 记录每条流水线的状态+时间戳 |
| 可视化仪表盘 | HTML 文件 | 自动生成，实时展示流水线进展 |
| 知识库 | IMA / 本地文件 | 存储素材、稿件、风格指南 |

## L0 调度器详细设计

### 触发方式

- 定时触发：工作日 08:00（RRULE: `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=8;BYMINUTE=0`）
- 手动触发：用户在 WorkBuddy 中运行"创建今日写作任务"（= 临时加开一篇）

### 执行逻辑

```python
def daily_content_plan():
    # Step 1: 确定今日内容类型
    weekday = get_today_weekday()
    if weekday == 6:  # 周日休息
        return "今日休息，不创建流水线"
    
    default_type = CONTENT_SCHEDULE[weekday]
    # 默认排期：周一→政策解读 | 周二→行业观察 | 周三→产品功能
    #           周四→痛点场景 | 周五→行业月报
    
    # v6 优化：动态排期
    content_type, adjust_reason = dynamic_adjust_type(default_type)
    
    # Step 2: 扫描素材，选择题材
    latest_briefs = get_latest_daily_briefs()
    topics = generate_topic_candidates(latest_briefs, content_type)
    
    # Step 3: 去重检查
    recent_topics = get_recent_topics(days=7)
    final_topic = select_best_topic(topics, exclude=recent_topics)
    
    # Step 4: 创建流水线实例
    pipeline_id = f"PL-{get_today_date()}-001"
    create_pipeline_directory(pipeline_id)
    
    # Step 5: 初始化状态文件
    status = {
        "pipeline_id": pipeline_id,
        "topic": final_topic,
        "content_type": content_type,
        "expert": match_expert(content_type),
        "current_stage": "选题就绪",
        "created_at": now(),
        "auto_confirm_minutes": 5,
        "stage_history": [
            {"stage": "新创建", "start": now(), "end": now()}
        ]
    }
    write_status_file(pipeline_id, status)
    
    # Step 6: 注册到全局注册表
    register_pipeline(pipeline_id, status)
    
    # Step 7: 通知
    notification = (
        f"📝 今日写作任务已安排\n"
        f"选题：{final_topic['title']}\n"
        f"类型：{content_type}\n"
        f"专家：{match_expert(content_type)}\n"
    )
    if adjust_reason:
        notification += f"⚠️ 排期调整：{default_type} → {content_type}（原因：{adjust_reason}）\n"
    notification += f"⏱ 5 分钟内未调整将自动确认选题"
    
    send_notification(notification)
    
    return f"流水线 {pipeline_id} 创建成功"
```

## L1 调度器详细设计

### 触发方式

- 定时触发：每小时 1 次（RRULE: `FREQ=HOURLY;INTERVAL=1`）
- 注意：WorkBuddy 不支持分钟级定时，最低粒度为小时

### 执行逻辑

```python
def pipeline_scheduler():
    # Step 0: 归档检查
    check_and_archive_expired_pipelines()
    
    # Step 1: 读取全局注册表
    registry = read_registry()
    
    # Step 2: 遍历所有活跃流水线
    for pipeline in registry["active_pipelines"]:
        pipeline_id = pipeline["id"]
        status = read_status_file(pipeline_id)
        stage = status["current_stage"]
        
        # Step 3: 根据当前阶段执行对应操作
        if stage == "选题就绪":
            if status["confirmed_at"]:
                advance_stage(pipeline_id, "选题确认")
            elif time_since(status["stage_start"]) > 5 * 60:
                advance_stage(pipeline_id, "选题确认")
                send_notification(f"⏰ 流水线 {pipeline_id} 选题已自动确认")
        
        elif stage == "选题确认":
            expert = status["expert"]
            skill = load_expert_skill(expert)
            draft = execute_creation(status["topic"], skill)
            write_draft(pipeline_id, draft)
            advance_stage(pipeline_id, "创作中")
        
        elif stage == "创作中":
            if draft_exists(pipeline_id):
                advance_stage(pipeline_id, "草稿完成")
        
        elif stage == "草稿完成":
            polisher = load_expert_skill("polisher")
            review = execute_polish(get_draft(pipeline_id), polisher)
            write_review(pipeline_id, review)
            advance_stage(pipeline_id, "润色中")
        
        elif stage == "润色中":
            if review_exists(pipeline_id):
                advance_stage(pipeline_id, "润色完成")
        
        elif stage == "润色完成":
            send_notification(f"📝 流水线 {pipeline_id} 终稿已就绪，请审批")
            advance_stage(pipeline_id, "审批中")
        
        elif stage == "审批中":
            if status["approved"]:
                publish_content(pipeline_id)
                advance_stage(pipeline_id, "已完成")
                status["completed_at"] = now()
            elif status["revision_requested"]:
                advance_stage(pipeline_id, "创作中")
        
        elif stage == "已完成":
            archive_to_knowledge_base(pipeline_id)
            update_expert_case_library(pipeline_id)
            deactivate_pipeline(pipeline_id)
        
        # Step 4: 更新状态文件
        save_status_file(pipeline_id, status)
    
    # Step 5: 重新生成仪表盘
    generate_dashboard()
```

## 数据层设计

```
知识库                        本地文件系统
├─ 品牌资料/                  ├─ pipelines/
│  ├─ 参考案例/              │  ├─ PL-20260731-001/
│  ├─ 产品介绍/              │  │  ├─ status.md
│  ├─ 行业动态/              │  │  ├─ topic.md
│  └─ 内容生产/              │  │  ├─ draft.md
│     ├─ 风格指南/           │  │  ├─ review.md
│     ├─ 选题库/             │  │  ├─ final.md
│     ├─ 内容草稿/           │  │  └─ performance.md
│     ├─ 待审批/             │  ├─ archive/
│     └─ 已发布/             │  │  └─ PL-20260701-001/
│                            ├─ registry.md
├─ registry.md               └─ dashboard.html
└─ dashboard.html
```

## 设计原则

1. **状态机驱动**：不依赖固定时间，上一阶段完成即触发下一阶段
2. **多流水线并行**：每天一条流水线，支持临时加开，互不干扰
3. **固定专家池**：5 类专家角色复用，Skill 文件持续迭代优化
4. **全流程可视**：每条流水线的每个阶段都有精确时间戳，随时可查
5. **数据闭环**：发布→效果追踪→复盘→优化专家 Skill→下一篇更好
