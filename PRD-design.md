# 总控台视觉升级PRD
文件: /tmp/workbench/index.html

## 问题
用户反馈"并不高级酷炫"。需整体提升质感。

## 改进项
1. 侧边栏: 毛玻璃效果(backdrop-filter blur) + 更精致间距
2. 顶部栏: 渐变背景 + 小动效
3. 卡片: 更精致的阴影 + hover微动效(transform 1px + shadow加深)
4. 概览统计: 数字更大更突出 + 渐变色图标
5. 任务列表: checkbox 动画 + 完成态划线动效
6. 项目进度条: 渐变色 + 动画
7. 知识文章卡片: 左侧彩色边框 + hover效果
8. 全局: 平滑 transition + 微妙的CSS变量优化(阴影层叠、色彩更丰富)

## 设计Token优化
- 主色变体: --accent2: #7c84e8 (更亮的蓝紫)
- 渐变: --grad: linear-gradient(135deg, #5e6ad2, #7c84e8)
- 微阴影: --sh-sm: 0 1px 2px rgba(0,0,0,.04)

## 不做的
- 不改HTML结构
- 不改JS逻辑
- 不引入外部CSS框架
