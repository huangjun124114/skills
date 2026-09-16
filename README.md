# Skills

家庭生活及工作中沉淀的 AI Agent Skills 合集。

每个 skill 是一个独立目录，遵循 `skills/<skill-name>/SKILL.md` 的通用约定，可直接被支持 Agent Skills 规范的工具（WorkBuddy / Claude Code 等）加载使用。

---

## 目录

| Skill | 说明 | 版本 |
|---|---|---|
| [brand-audit-expert](skills/brand-audit-expert/) | 品牌营销全链路审计专家 —— 四维 12 项指标体检 + 根因访谈，输出《品牌现状诊断书》 | — |
| [content-ops-automation](skills/content-ops-automation/) | 通用内容自动化运营框架 —— 采集→选题→创作→润色→审批→发布→复盘七阶段流水线 | 4.2 |
| [course-notes-html-report](skills/course-notes-html-report/) | 培训课程多源材料（录音转写、纪要、课件、研报）整合为 HTML 报告 | — |
| [doc-archive-organizer](skills/doc-archive-organizer/) | 大规模历史文档归档的知识化 —— 只读诊断 → 搬迁去重 → 三层知识索引 | — |
| [feishu-doc-to-markdown](skills/feishu-doc-to-markdown/) | 飞书云文档（wiki / docx）导出为可独立分发的本地 markdown，附件本地化 | — |
| [html-data-report](skills/html-data-report/) | 自包含深色主题 HTML 数据分析报告构建与视觉验证（含窄屏溢出检测） | — |
| [html-deploy](skills/html-deploy/) | 把单文件 HTML 快速发布到公网并返回可分享链接 | 1.3.1 |
| [humanizer](skills/humanizer/) | 消除文本中的 AI 生成痕迹，让表达更像自然的人类写作 | 2.1.1 |
| [ima-skills](skills/ima-skills/) | 腾讯 ima 知识库相关能力 | 1.1.9 |
| [industry-research-6](skills/industry-research-6/) | 六环节行业研究框架 —— 分六轮交付，最终整合为单文件 HTML 报告 | — |
| [library-page-archive](skills/library-page-archive/) | 把已托管的资料库 HTML 页面完整复刻到本地并派生 Markdown 归档版 | — |
| [libtv-cli](skills/libtv-cli/) | LibTV 官方 CLI（libtv）—— 命令行操作 LibTV 画布 / 项目 / 节点 / 模型 | — |
| [marketing-demand-translator](skills/marketing-demand-translator/) | 爆款话术炼金炉 —— 痛点·爽点·痒点方法论，卖点翻译为下单话术 | 1.2.3 |
| [photo-archive-organizer](skills/photo-archive-organizer/) | 家庭相册整理专家 —— 多源合并 / 筛选归档、六道检验闸门 | 2.0.0 |
| [thirdparty-plugin-install-audit](skills/thirdparty-plugin-install-audit/) | 第三方插件 / Skill / MCP 安装前的安全审计 + 安装 + 验证流程 | — |

---

## 使用方式

### 方式一：克隆后手动安装

```bash
git clone https://github.com/huangjun124114/skills.git
# 把需要的 skill 目录复制到你的 skills 目录，例如
cp -r skills/libtv-cli ~/.workbuddy/skills/
```

单取某一个 skill 时，可用稀疏检出避免拉全量：

```bash
git clone --filter=blob:none --sparse https://github.com/huangjun124114/skills.git
cd skills
git sparse-checkout set skills/libtv-cli
```

### 方式二：直接下载

进入对应 skill 目录，用 GitHub 的 `Download ZIP`，或直接取 raw 文件。

---

## 仓库结构

```
skills/
├── <skill-name>/
│   ├── SKILL.md            # 必需：skill 主文档（YAML frontmatter + 正文）
│   ├── scripts/            # 可选：可执行脚本
│   ├── references/         # 可选：按需加载的参考文档
│   ├── assets/             # 可选：模板、图片等静态资源
│   └── ...
└── ...
```

## 相关仓库

部分 skill 早期以独立仓库维护，已迁移至本仓库：

| 原仓库 | 现位置 | 状态 |
|---|---|---|
| [content-ops-automation](https://github.com/huangjun124114/content-ops-automation) | [skills/content-ops-automation](skills/content-ops-automation/) | 已归档 |
| [photo-archive-organizer](https://github.com/huangjun124114/photo-archive-organizer) | [skills/photo-archive-organizer](skills/photo-archive-organizer/) | 已归档 |

## License

[MIT](LICENSE)
