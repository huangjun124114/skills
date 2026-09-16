# 通知模板集

> 支持企微 Bot / 邮件 / 钉钉等通知渠道

---

## 1. 今日写作任务已安排

```
📝 今日写作任务已安排

流水线：{pipeline_id}
选题：{topic_title}
类型：{content_type}
专家：{expert_name}
预计完成：{estimated_completion}

如需调整，请在 5 分钟内回复"修改选题"
```

## 2. 排期调整通知

```
⚠️ 排期调整通知

流水线：{pipeline_id}
原计划：{original_type}
调整为：{adjusted_type}
原因：{adjust_reason}
选题：{topic_title}

如需恢复原计划，请在 5 分钟内回复"恢复原计划"
```

## 3. 选题自动确认

```
⏰ 选题已自动确认

流水线：{pipeline_id}
选题：{topic_title}
类型：{content_type}
专家：{expert_name}

已超过 5 分钟未调整，选题已自动确认并开始创作
```

## 4. 终稿已就绪，请审批

```
📝 终稿已就绪，请审批

流水线：{pipeline_id}
标题：{article_title}
字数：{word_count} 字
创作专家：{creator_expert}
润色专家：{polisher_expert}

📖 预览链接：{preview_url}

请回复"通过"或修改意见
```

## 5. 审批通过，文章已发布

```
✅ 文章已发布

流水线：{pipeline_id}
标题：{article_title}
发布平台：{platforms}
发布时间：{publish_time}
文章链接：{article_url}

请在 24 小时后查看效果数据
```

## 6. 审批驳回，需修改

```
❌ 审批驳回，需修改

流水线：{pipeline_id}
标题：{article_title}
驳回原因：{rejection_reason}
修改建议：{revision_suggestions}

请重新创作后再次提交审批
```

## 7. 周度复盘报告

```
📊 上周内容运营复盘

产出：{total_count} 篇 | 完成：{completed_count} 篇 | 平均耗时：{avg_duration}
平均阅读量：{avg_views} | 最佳：《{best_article}》({best_views})
最佳专家：{best_expert}

建议：{recommendations}
```

## 8. Skill 进化通知

```
🔄 Skill 已进化（{old_version} → {new_version}）

分析范围：最近 {analysis_count} 篇文章
最佳专家：{best_expert}（平均阅读量 {best_avg_views}）
最佳类型：{best_type}（点击率 {best_click_rate}）

优化内容：
{optimization_details}

预期效果：{expected_improvement}
```

---

## 使用说明

1. 将模板中的 `{变量名}` 替换为实际值
2. 根据通知渠道选择合适的格式（企微 Bot 支持 Markdown，邮件支持 HTML）
3. 可根据品牌风格调整 emoji 使用和措辞
