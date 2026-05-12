数据流与转换
============

本章描述数据如何从原始 HTTP 响应经过管线流向最终的 JSON 和 Markdown 文件。

站点分类
--------

43 个活跃站点按内容更新频率和技术可访问性分为三组：

**RSS 优先组（约 21 个站点）：**
有可用 RSS 源的站点。抓取器使用 ``curl + feedparser``——最快路径，资源消耗最低。只收录最近 7 天内发布的文章；旧条目直接丢弃，遇到第一个过期文章立即停止分页。

**Playwright 组（约 22 个站点）：**
没有可靠 RSS，或 RSS 返回历史档案（例如 Fluid Radio——671 条 2013–2022 年的历史条目）。抓取器启动无头 Chromium 浏览器（``browser_navigate``），开启隐身模式，访问评论列表页，最多抓取前 2 个列表页。如果第 1 页所有条目都超过 7 天，则不访问第 2 页。

**搜索降级组：**
付费墙站点（如 The Wire）或被 Cloudflare JS 验证拦截的站点。抓取器降级为 ``web_search``，同样受 7 天窗口约束。

**特殊情况——Fluid Radio：**
该站 RSS 全部是 2013–2022 年的档案内容。在 sites.json 中标记 ``crawl_strategy: "skip"``，不参与正常抓取。聚合器改为每次运行从档案中随机抽取 2–3 条，打上 ``[Fluid Radio Archive]`` 标签，让档案内容缓慢进入推荐池。

抓取器输出格式
--------------

每个抓取器向 workspace 目录写入一个 JSON 文件，名为 ``{site_id}_reviews.json``。

.. code-block:: json

   {
     "site_id": "the_wire",
     "crawl_date": "2026-05-12",
     "crawl_strategy": "rss",
     "reviews": [
       {
         "album": "Electric Baker",
         "artist": "Mats Gustafsson",
         "score": 9.0,
         "url": "https://thewire.co.uk/reviews/abc123",
         "source": "the_wire",
         "pub_date": "2026-05-11",
         "tags": ["free jazz", "electroacoustic"],
         "excerpt": "Gustafsson electric Baker pulsing modal extrapolation",
         "site_id": "the_wire",
         "crawl_status": "success"
       }
     ]
   }

若站点没有新文章，文件内容为空数组：

.. code-block:: json

   { "site_id": "boomkat", "reviews": [], "crawl_status": "no_new_articles" }

串行-并行混合示意图
-------------------

下图展示 6 个站点（BATCH_SIZE=2）的完整父子门控链。43 个站点的模式同理，在 22 个批次中重复。

.. mermaid::
   :caption: 完整父子门控链——6 个站点示例（BATCH_SIZE=2）

   %%{init: { 'theme': 'default', 'flowchart': { 'curve': 'basis' } } }%%
   graph TB
       START["START<br/>no parent"] --> BA1["Batch A<br/>site:1 site:2"]
       BA1 -->|"parents done"| BA2["Batch B<br/>site:3 site:4"]
       BA2 -->|"parents done"| BA3["Batch C<br/>site:5 site:6"]
       BA3 -.->|"all 43 done"| AGG["Aggregator<br/>parents: all 43 scrapers"]

       BA1 -->|"site:1 writes"| F1["{site_id}_reviews.json"]
       BA1 -->|"site:2 writes"| F2["{site_id}_reviews.json"]
       BA2 -->|"site:3 writes"| F3["{site_id}_reviews.json"]
       BA2 -->|"site:4 writes"| F4["{site_id}_reviews.json"]
       BA3 -->|"site:5 writes"| F5["{site_id}_reviews.json"]
       BA3 -->|"site:6 writes"| F6["{site_id}_reviews.json"]

       F1 & F2 & F3 & F4 & F5 & F6 -->|"all JSON files<br/>in workspace"| AGG

       style START fill:#e8f5e9
       style AGG fill:#fff9c4
       style BA1 fill:#c8e6c9
       style BA2 fill:#c8e6c9
       style BA3 fill:#c8e6c9

数据转换管线
-----------

聚合器对原始抓取器输出执行四个独立的转换：

.. mermaid::
   :caption: 聚合器内部数据转换

   %%{init: { 'theme': 'default' } }%%
   flowchart LR
       subgraph "1. 收集与合并"
           J1["{site1}_reviews.json"]
           J2["{site2}_reviews.json"]
           J3["{site3}_reviews.json"]
           JN["… × 43"]
           J1 & J2 & J3 & JN --> MERGE["Concatenated list<br/>N total entries"]
       end

       subgraph "2. 去重"
           MERGE --> DEDUP["Dedupe by<br/>(album + artist) key<br/>keep highest score"]
           DEDUP --> UNIQ["U unique entries<br/>U ≤ N"]
       end

       subgraph "3. 评分与分类"
           UNIQ --> CLASS["Classify: review / feature / tracklist"]
           CLASS --> SCORE["Apply scoring formula<br/>Compute total_score"]
           SCORE --> FILTER["Split by score"]
       end

       subgraph "4. 渲染与持久化"
           FILTER --> AGG_JSON["aggregated.json<br/>(all U entries)"]
           FILTER --> FILT_JSON["filtered.json<br/>(score ≥ 6)"]
           FILTER --> MD["{DATE}.md<br/>(score ≥ 6, full detail)"]
           FILTER --> TOP20["recommend/{DATE}.md<br/>(top 20 by score)"]
       end

       style MERGE fill:#e3f2fd
       style DEDUP fill:#f3e5f5
       style SCORE fill:#fff9c4
       style AGG_JSON fill:#c8e6c9
       style FILT_JSON fill:#c8e6c9
       style MD fill:#c8e6c9
       style TOP20 fill:#e8f5e9

Git Push 流程
------------

写入 4 个输出文件后，聚合器在 ``music-record`` 仓库内执行 git 提交和推送：

.. code-block:: bash

   cd ~/music-record

   git add \
     2026/05/2026-05-12/aggregated.json \
     2026/05/2026-05-12/filtered.json \
     2026/05/2026-05-12/2026-05-12.md \
     recommend/2026-05-12.md

   git commit -m "auto: 2026-05-12 daily recs"
   git push origin main

workspace 目录是 git 工作树内的日期命名子目录，因此所有文件路径都相对于 ``~/music-record``，推送后立即更新共享仓库。

.. mermaid::
   :caption: Git push 流程

   %%{init: { 'theme': 'default' } }%%
   flowchart LR
       WS["workspace dir<br/>2026/05/2026-05-12/"] --> FILES["4 output files<br/>aggregated.json<br/>filtered.json<br/>2026-05-12.md<br/>recommend/2026-05-12.md"]
       FILES --> ADD["git add"]
       ADD --> COMMIT["git commit<br/>auto: {DATE} daily recs"]
       COMMIT --> PUSH["git push origin main"]
       PUSH --> GH["GitHub<br/>pty819/music-record"]
       GH --> ACTIONS["GitHub Actions<br/>(if configured)"]
       GH --> TG["Telegram<br/>top-20 push"]

       style PUSH fill:#e8f5e9
       style GH fill:#c8e6c9
