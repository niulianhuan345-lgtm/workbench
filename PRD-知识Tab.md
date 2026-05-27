# 总控台知识Tab 改造 - 简明版

## 目标文件
/tmp/workbench/index.html

## 数据源
- 当前 `data/knowledge-v2.json` 结构：
  - `platforms[]` — 4个平台（tmall, jd, xhs, vip）
  - 每个平台有：`knowledge_summary`, `articles[]`, `daily_log[]`, `stats`
  - `internal[]` — 内部知识（aione, analysis）

## 核心要求：知识Tab显示以下内容

### 左侧导航
- 分组「🌐 平台情报」下列出4个平台：🐱 天猫、🐕 京东、📕 小红书、🛍️ 唯品会
- 分组「🏠 内部知识」下列出内部条目
- 点击切换右侧详

### 右侧详情（选中平台后显示）
1. 头部：平台名 + 来源 + 抓取方式
2. 学习进度条（如果 stats.total_courses > 0）
3. 文章卡片列表（如果 articles 不为空）—— 每张卡显示标题、标签、讲师、🔗原文链接
4. 知识点总结（如果 articles 为空但有 knowledge_summary）
5. 变更日志 daily_log

## 兼容要求
- 如果 knowledge-v2.json 不存在，降级用 knowledge.json
- 不要改动任务Tab、项目Tab、系统Tab
- 保持现有 CSS Token

## 验证
完成后检查：
1. grep "knowledge-v2" index.html （数据源正确）
2. grep "platforms" index.html （v2渲染逻辑存在）
3. 文件大小合理（>50KB）
