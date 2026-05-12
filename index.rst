Music Daily Recs — Pipeline Ebook
==================================

本电子书详细记录了 music-daily-recs 调研管线的架构、数据流、并发模型和输出行为。系统运行于 Hermes 任务编排框架，每天北京时间 04:00 自动抓取 43 个音乐评论站，聚合评分后推送到 Telegram。

.. toctree::
   :maxdepth: 3
   :numbered:

   chapter1_architecture
   chapter2_pipeline
   chapter3_dataflow
   chapter4_output

简介
----

**管线做什么：**

1. cron job 每天北京时间 04:00 触发
2. 批处理脚本以父任务门控方式创建 43 个看板任务，每次并行 2 个
3. 每个抓取器向 ``music-record`` git 仓库的日期子目录写入 ``{site_id}_reviews.json``
4. 最终聚合任务读取全部 43 个 JSON 文件，去重、评分，写入三个输出文件并 git commit/push
5. Telegram 推送 top-20 精选推荐给订阅者

**关键数字：**

- **43** 个活跃音乐评论站（Boomkat、Syrphe、Textura 因不可访问已跳过）
- **43** 个抓取任务 + **1** 个聚合任务，每次运行
- **2** 个任务并发执行（父任务门控分批）
- **3** 个输出文件：``aggregated.json``、``filtered.json``、``{DATE}.md``
- **1** 个 top-20 精选推送 Telegram

.. mermaid::
   :caption: 管线高层概览

   %%{init: { 'theme': 'default', 'themeVariables': { 'fontSize': '14px' } } }%%
   graph LR
       C["⏰ Cron 04:00<br/>Beijing"] --> B["kanban-batch-scrape.py"]
       B --> S1["scraper task 1"]
       B --> S2["scraper task 2"]
       B --> S3["scraper task …"]
       B --> S43["scraper task 43"]
       S1 --> A1["{site_id}_reviews.json"]
       S2 --> A2["{site_id}_reviews.json"]
       S43 --> A43["{site_id}_reviews.json"]
       A1 --> AGG["aggregator task"]
       A2 --> AGG
       A43 --> AGG
       AGG --> G["git push<br/>music-record repo"]
       AGG --> TG["Telegram top-20"]
