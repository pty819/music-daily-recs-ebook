完整管线详解
=============

本章追踪一次日常运行的全流程，从 cron 触发到 git push。

触发：北京时间 04:00
--------------------

``music-daily-recs`` skill 声明了一个 ID 为 ``6fd93b4a4c4c`` 的 cron job：

.. code-block:: yaml

   cron_job: 6fd93b4a4c4c（每天 04:00 北京时间自动运行 pipeline + git push）

cron 触发时，Hermes 为 ``orchestrator`` profile 创建一个新的 agent 会话，加载 ``music-daily-recs`` skill，并将完整管线 prompt 注入会话消息。编排器然后顺序执行各个步骤——编排逻辑本身不委托给子 agent。

选择凌晨 04:00 是因为大多数音乐评论网站在夜间（美国/欧洲时区）更新内容，所以到北京时间 04:00，前一天的评论已全部发布。

第零步：积压清理（永远是第一步）
-------------------------------

在任何其他操作之前，编排器必须清除上次运行遗留的过时 ``◻ todo`` 抓取任务：

.. code-block:: bash

   hermes kanban list | grep "◻" | grep "scrape:" | awk '{print $2}' | while read id; do
     hermes kanban archive "$id"
   done

没有这一步，看板每次运行后会堆积 43+ 个过时任务。三天后就会看到 120+ 个幽灵任务，调度器也可能对父子关系产生混淆。

编排器此时还会验证 ``auth.json``——确认只有 ``minimax-cn`` provider 存在，且 scraper profile 配置指向 ``minimax-cn``。

第一步：同步 sites.json
------------------------

编排器从 ``music-record`` git 仓库拉取最新的站点配置：

.. code-block:: bash

   cd ~/.minimax/music-sites && git pull origin main

文件 ``~/.minimax/music-sites/sites.json`` 定义了全部 46 个配置的站点：

- **43 个活跃** — ``crawl_strategy`` 为 ``rss`` 或 ``playwright_headless``
- **3 个跳过** — Boomkat、Syrphe、Textura（``crawl_strategy: "skip"`` — 不可访问）

返回付费墙响应的站点会在 JSON 中被标记 ``status: "paywalled"``（例如 The Wire）且不会被重试。

第二步：批处理脚本执行
----------------------

这是正确创建 43 个抓取任务的关键步骤。

**⚠️ 错误做法：** 循环调用 ``kanban create`` 43 次，不做父任务门控。
这会同时启动 43 个无头浏览器 → OOM 崩溃。

**✅ 正确做法：** ``kanban-batch-scrape.py``。

.. code-block:: bash

   python3 ~/.local/bin/kanban-batch-scrape.py --confirm

脚本内部逻辑（简化版）：

.. code-block:: python

   BATCH_SIZE = 2
   batches = [sites[i:i+BATCH_SIZE] for i in range(0, len(sites), BATCH_SIZE)]

   prev_task_ids = []
   for batch_idx, batch in enumerate(batches):
       parents = list(prev_task_ids)  # 首批为空

       task_ids = []
       for site in batch:
           tid = hermes_create(
               title=f"scrape: {site['name']}",
               body=scraper_body(site),
               assignee="scraper",
               parents=parents if parents else None,
               skills=["kanban-worker"],
               workspace=f"dir:~/music-record/2026/{MM}/{DATE}",
           )
           task_ids.append(tid)

       prev_task_ids = list(task_ids)

第一批**没有父任务**——两个任务立即分发。
第二批设置 ``parents=[t1a, t1b]``——调度器等待两者都 ``✓ done``。
第三批设置 ``parents=[t2a, t2b]``，以此类推。

全部 43 个抓取任务创建完成后，脚本创建**聚合任务**，设置 ``parents=all_task_ids``——直到所有抓取器完成才会分发。

执行 ``--confirm`` 后的结果：

- **22 批 × 2 = 44** 次任务创建，但实际只有 43 个抓取器（有一批只有 1 个站点）
- **1 个聚合器**，依赖 43 个父任务

第三步：抓取器执行
------------------

每个抓取任务运行在 ``scraper`` profile worker 内部。worker 的 LLM 读取任务 ``body`` 并执行抓取指令。所有站点的任务 body 是同一个模板；站点专属参数（URL、策略、标签）通过字符串插值注入。

**抓取策略：**

- ``rss`` — ``curl + feedparser``，解析 XML，筛选最近 7 天
- ``playwright_headless`` — ``browser_navigate`` 无头 + 隐身模式，最多 2 页
- ``search_fallback`` — ``web_search``（付费墙/Cloudflare 降级）

所有策略都强制执行 **7 天窗口**：超过 7 天的文章被跳过，遇到第一个过时文章立即停止分页。

**没有新文章的站点** 返回空 JSON 数组 ``[]``——这是正常行为，不是错误。

每个抓取器的输出：一个文件 ``{site_id}_reviews.json``，直接写入 workspace 目录（即 git 仓库内的日期子目录）：

.. code-block:: json

   [
     {
       "album": "The Other Side of Time",
       "artist": "Catherine Christer Hennix",
       "score": 9.5,
       "url": "https://example.com/review/123",
       "source": "the_wire",
       "pub_date": "2026-05-11",
       "tags": ["experimental", "minimalism"],
       "excerpt": "A searing modal extrapolation…",
       "site_id": "the_wire",
       "crawl_status": "success"
     }
   ]

抓取完成后调用 ``kanban_complete(summary="scraped N reviews from {name} (last 7 days)", metadata={...})``。

第四步：聚合器执行
------------------

聚合任务在所有 43 个抓取器的父任务都 ``✓ done`` 之前不会分发。它运行在同一个 ``scraper`` profile（相同认证、相同 worker skill），读取共享的 workspace 目录。

**聚合器步骤：**

1. **收集** — 从 workspace 读取所有 ``*_reviews.json`` 文件
2. **合并** — 将所有 JSON 数组合并为一个列表
3. **去重** — 以 ``(album + artist)`` 为 key；若发现重复，保留得分更高的来源
4. **分类** — 分配 ``type``：``review``（有 album + artist）、``feature``（有 artist 但无 album，或 album 为特辑标题如"本周再版"）、``tracklist``（来自 The Wire）
5. **评分** — 应用评分公式（见第四章）
6. **过滤** — 拆分为 ``aggregated.json``（所有唯一评论）和 ``filtered.json``（得分 ≥ 6）
7. **渲染 markdown** — 写入 ``{DATE}.md``（完整列表，得分 ≥ 6）和 ``recommend/{DATE}.md``（top 20，得分 ≥ 6，按得分降序）
8. **Git push** — 提交并推送 4 个文件到 ``pty819/music-record``
9. **kanban_complete** — 标记完成

第五步：Telegram 推送
----------------------

编排器读取 ``recommend/{DATE}.md`` 文件，将 top-20 条目发送到 Telegram 频道。这是 cron job prompt 的最后一步。

**已知问题：** 若聚合任务崩溃（父任务门控 bug），Telegram 推送也会被跳过，因为它目前嵌入在聚合任务的 body 指令中，而不是作为独立任务。

.. mermaid::
   :caption: 端到端管线流程

   %%{init: { 'theme': 'default' } }%%
   flowchart TB
       subgraph "编排器（定时 agent）"
           A0["Step 0<br/>Archive stale tasks"]
           A1["Step 1<br/>git pull sites.json"]
           A2["Step 2<br/>kanban-batch-scrape.py"]
           A3["Step 4<br/>Monitor scrapers"]
           A4["Step 5<br/>Push Telegram top-20"]
           A0 --> A1 --> A2 --> A3 --> A4
       end

       subgraph "Scraper profile workers（2 并发）"
           S1["Batch 1 scrapers"]
           S2["Batch 2 scrapers"]
           SN["Batch N scrapers"]
           S1 --> S2 --> SN
       end

       subgraph "Aggregator（scraper profile）"
           AGG["Read all JSON → Dedup → Score → Write files → Git push"]
       end

       A2 -->|"creates 43 tasks<br/>+ 1 aggregator"| S1
       SN -->|"all 43 done<br/>parent unblocked"| AGG
