# Music Daily Recs — Pipeline Ebook

**在线阅读：** https://pty819.github.io/music-daily-recs-ebook/

> 本电子书详细记录了 music-daily-recs 调研管线的架构、数据流、并发模型和输出行为。系统运行于 Hermes 任务编排框架，每天北京时间 04:00 自动抓取 43 个音乐评论站，聚合评分后推送到 Telegram。

---

## 快速概览

- **43** 个活跃音乐评论站（Boomkat、Syrphe、Textura 因不可访问已跳过）
- **43** 个抓取任务 + **1** 个聚合任务，每次运行
- **2** 个任务并发执行（父任务门控）
- **3** 个输出文件：`aggregated.json`、`filtered.json`、`{DATE}.md`
- **1** 个精选 20 条推送到 Telegram

---

## 内容结构

| 章节 | 主题 |
|------|------|
| [Chapter 1 — Architecture](https://pty819.github.io/music-daily-recs-ebook/chapter1_architecture.html) | 整体架构与组件 |
| [Chapter 2 — Pipeline](https://pty819.github.io/music-daily-recs-ebook/chapter2_pipeline.html) | cron → kanban → scraper 执行流 |
| [Chapter 3 — Dataflow](https://pty819.github.io/music-daily-recs-ebook/chapter3_dataflow.html) | JSON 数据在各阶段的变化 |
| [Chapter 4 — Output](https://pty819.github.io/music-daily-recs-ebook/chapter4_output.html) | 最终输出与 Telegram 推送格式 |

---

## 本地构建

```bash
# 安装依赖
pip install sphinx sphinxcontrib-mermaid sphinx_rtd_theme

# 构建 HTML
sphinx-build -b html . _build/html

# 本地预览
cd _build/html && python -m http.server 8080
```

---

## 相关项目

- **music-record** — 每日乐评原始数据与输出：https://github.com/pty819/music-record
- **hermes-agent** — 本系统运行的 Agent 框架
