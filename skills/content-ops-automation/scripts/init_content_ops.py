#!/usr/bin/env python3
"""
内容自动化运营框架 - 项目初始化脚本

用法：
    python init_content_ops.py <项目根目录>

示例：
    python init_content_ops.py /path/to/project

功能：
    1. 创建标准目录结构（content-pipeline、brand-context、skills）
    2. 从模板文件初始化配置文件和仪表盘
    3. 创建示例专家 Skill 文件
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime


def get_skill_assets_dir() -> Path:
    """获取 Skill 的 assets 目录路径"""
    return Path(__file__).parent.parent / "assets"


def create_directory_structure(project_root: Path):
    """创建项目目录结构"""
    print("📁 创建目录结构...")
    
    dirs = [
        "content-pipeline/pipelines/archive",
        "content-pipeline/config",
        "brand-context/产品介绍",
        "brand-context/参考案例",
        "brand-context/行业动态",
        "brand-context/风格指南",
        "skills",
    ]
    
    for dir_path in dirs:
        full_path = project_root / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {dir_path}")


def init_config_files(project_root: Path, assets_dir: Path):
    """初始化配置文件"""
    print("\n📄 初始化配置文件...")
    
    # 复制模板文件
    templates = {
        "registry-template.md": "content-pipeline/registry.md",
        "config-template.md": "content-pipeline/config/配置参数表.md",
        "dashboard-template.html": "content-pipeline/dashboard.html",
    }
    
    for template_name, target_path in templates.items():
        src = assets_dir / template_name
        dst = project_root / target_path
        
        if src.exists():
            content = src.read_text(encoding="utf-8")
            # 替换占位符
            content = content.replace("{timestamp}", datetime.now().strftime("%Y-%m-%d %H:%M"))
            content = content.replace("{update_time}", datetime.now().strftime("%Y-%m-%d %H:%M"))
            content = content.replace("{total_count}", "0")
            content = content.replace("{completed_count}", "0")
            content = content.replace("{active_count}", "0")
            content = content.replace("{avg_duration}", "0h")
            content = content.replace("{total_views}", "0")
            content = content.replace("{avg_engagement}", "0%")
            content = content.replace("{total_leads}", "0")
            
            # 清空模板内容（保留结构）
            if "active_pipelines" in content:
                content = content.replace("{active_pipelines}", "<!-- 暂无活跃流水线 -->")
            if "completed_pipelines" in content:
                content = content.replace("{completed_pipelines}", "<!-- 暂无已完成流水线 -->")
            if "activity_log" in content:
                content = content.replace("{activity_log}", "<!-- 暂无动态 -->")
            
            dst.write_text(content, encoding="utf-8")
            print(f"   ✅ {target_path}")
        else:
            print(f"   ⚠️  模板文件不存在: {template_name}")
    
    # 创建内容排期策略文件
    schedule_content = """# 内容排期策略

> 最后更新：{timestamp}

## 默认排期

| 星期 | 内容类型 | 匹配专家 | 备注 |
|------|---------|---------|------|
| 周一 | 政策解读 | 📋 政策解读者 | 周末政策汇总 |
| 周二 | 行业观察 | 📰 行业观察家 | 行业动态跟踪 |
| 周三 | 产品功能 | 🚀 产品布道师 | 产品更新发布 |
| 周四 | 痛点场景 | 💡 痛点猎手 | 客户故事挖掘 |
| 周五 | 行业月报 | 📰 行业观察家 | 本周行业汇总 |
| 周六 | 休息 | - | 不创建流水线 |
| 周日 | 休息 | - | 不创建流水线 |

## 动态排期优先级

| 优先级 | 触发条件 | 行为 |
|--------|---------|------|
| 1（最高） | 今日素材含热点事件 | 直接匹配热点对应类型 |
| 2 | 某类素材特别丰富（≥5 条） | 优先使用素材最丰富的类型 |
| 3 | 默认类型近 7 天已用 ≥3 次 | 切换至使用最少的类型 |
| 4（默认） | 以上均不触发 | 使用星期排期默认建议 |
""".replace("{timestamp}", datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    schedule_path = project_root / "content-pipeline/config/内容排期策略.md"
    schedule_path.write_text(schedule_content, encoding="utf-8")
    print(f"   ✅ content-pipeline/config/内容排期策略.md")


def init_expert_skills(project_root: Path, assets_dir: Path):
    """初始化专家 Skill 文件"""
    print("\n👥 初始化专家 Skill 文件...")
    
    experts = [
        {
            "name": "policy-writer",
            "title": "政策解读者",
            "emoji": "📋",
            "type": "政策解读、法规分析",
            "ability": "政策拆解→影响分析→建议"
        },
        {
            "name": "industry-writer",
            "title": "行业观察家",
            "emoji": "📰",
            "type": "行业动态、市场趋势",
            "ability": "数据整合→趋势判断→洞察"
        },
        {
            "name": "product-writer",
            "title": "产品布道师",
            "emoji": "🚀",
            "type": "产品功能、体验升级",
            "ability": "功能翻译→场景演示→价值传递"
        },
        {
            "name": "painpoint-writer",
            "title": "痛点猎手",
            "emoji": "💡",
            "type": "场景痛点、客户故事",
            "ability": "故事构建→共情触发→方案植入"
        },
        {
            "name": "polisher",
            "title": "内容打磨师",
            "emoji": "🔍",
            "type": "所有类型的润色+合规",
            "ability": "去 AI 味→事实核查→品牌一致性"
        },
    ]
    
    for expert in experts:
        skill_content = f"""---
name: {expert['name']}
version: 1.0
description: {expert['title']}
last_updated: {datetime.now().strftime('%Y-%m-%d')}
---

# 角色：{expert['title']}

## 身份定位
你是内容运营团队的「{expert['title']}」，专精于{expert['type']}。你的核心能力是{expert['ability']}。

## 写作模板

### 标题公式
- 模式 A：[待补充]
- 模式 B：[待补充]

### 结构模板
```
开头（150-200 字）→ [待补充]
01 ...（300-400 字）→ [待补充]
02 ...（300-400 字）→ [待补充]
03 ...（300-400 字）→ [待补充]
结尾（100-150 字）→ [待补充]
```

### 产品植入策略
[待补充]

### 合规检查清单
- [ ] 内容准确，无事实错误
- [ ] 不出现竞品名称
- [ ] 符合品牌风格指南
- [ ] 字数 1500-2000

### 历史案例库
| 日期 | 选题 | 阅读量 | 经验总结 |
|------|------|--------|---------|
| （待填充） | | | |

### 迭代记录
- v1.0 ({datetime.now().strftime('%Y-%m-%d')}): 初始版本
"""
        
        skill_path = project_root / f"skills/{expert['name']}.md"
        skill_path.write_text(skill_content, encoding="utf-8")
        print(f"   ✅ skills/{expert['name']}.md")


def print_next_steps(project_root: Path):
    """打印后续步骤"""
    print("\n" + "=" * 60)
    print("✅ 项目初始化完成！")
    print("=" * 60)
    print(f"\n项目路径: {project_root}")
    print("\n📋 后续步骤:")
    print("  1. 在 brand-context/ 目录下放置品牌资料（产品介绍、参考案例等）")
    print("  2. 完善 skills/ 目录下的专家 Skill 文件（补充写作模板、产品植入策略等）")
    print("  3. 配置 WorkBuddy Automation（L0 每日写作计划 + L1 流水线调度器）")
    print("  4. 运行第一条流水线验证全流程")
    print("\n📚 详细文档请参考 Skill 的 references/ 目录:")
    print("  - architecture.md: 三层调度架构规范")
    print("  - pipeline-spec.md: 流水线状态机定义")
    print("  - expert-pool-pattern.md: 专家池设计模式")
    print("  - dispatch-rules.md: 调度规则与动态排期策略")
    print("  - evolution-protocol.md: 自进化协议")


def main():
    if len(sys.argv) < 2:
        print("用法: python init_content_ops.py <项目根目录>")
        print("示例: python init_content_ops.py /path/to/project")
        sys.exit(1)
    
    project_root = Path(sys.argv[1]).resolve()
    
    # 检查目录是否已存在
    if project_root.exists() and any(project_root.iterdir()):
        print(f"⚠️  目录已存在且非空: {project_root}")
        response = input("是否继续？(y/N): ")
        if response.lower() != 'y':
            print("已取消")
            sys.exit(0)
    
    # 创建项目根目录
    project_root.mkdir(parents=True, exist_ok=True)
    
    # 获取 assets 目录
    assets_dir = get_skill_assets_dir()
    if not assets_dir.exists():
        print(f"❌ assets 目录不存在: {assets_dir}")
        print("请确保在 Skill 目录下运行此脚本")
        sys.exit(1)
    
    print(f"🚀 初始化内容自动化运营项目: {project_root}\n")
    
    # 执行初始化
    create_directory_structure(project_root)
    init_config_files(project_root, assets_dir)
    init_expert_skills(project_root, assets_dir)
    
    # 打印后续步骤
    print_next_steps(project_root)


if __name__ == "__main__":
    main()
