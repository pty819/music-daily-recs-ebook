Hermes 架构概述
================

music-daily-recs skill 运行在 **Hermes** 内部——一个围绕看板_board 构建的智能任务编排框架，包含定时触发器、skill 加载器和委托调度机制。

核心概念
--------

**Agent（智能体）**

Agent 是一个有名字的执行上下文，拥有自己的身份、认证凭证和工具访问权限。管线使用两个 agent profile：

- ``orchestrator`` — 定时 agent，拥有每日管线运行的所有权：清理积压任务、同步 ``sites.json``、调用批处理脚本、推送 Telegram
- ``scraper`` — 所有 43 个站点抓取任务和最终聚合任务共用同一个 profile；携带共享的 ``auth.json``（单一 ``minimax-cn`` provider）和 kanban worker skill

**Skill（技能）**

Skill 是存储在 ``~/.hermes/skills/`` 下的 YAML/JSON 文档，定义了一个 agent 能做什么。``music-daily-recs`` skill 将完整管线描述为一系列步骤（积压清理 → sync sites → 批量创建 → 监控 → Telegram 推送）。Skill 在任务分发时加载到 agent 上下文中。

**Kanban（看板）**

Kanban 板是 Hermes 的任务队列，每个任务包含：

- ``id`` — 唯一任务标识符
- ``title`` — 人类可读标签
- ``body`` — 完整指令文本（传入 agent 的 LLM）
- ``assignee`` — 由哪个 agent profile 执行
- ``parents`` — 必须先完成才能调度本任务的任务 ID 列表
- ``children`` — 自动推导：本任务作为父任务的所有任务
- ``status`` — ``◻ todo``、``▶ ready``、``✓ done``、``⊘ blocked``
- ``skills`` — 分发路由所需的 skill 标签
- ``workspace`` — 文件 I/O 的工作目录

**Cron（定时任务）**

Hermes cron job（skill 元数据中的 ``cron_job``）是定时触发器，在固定时钟时间将 prompt 注入 agent 会话。``music-daily-recs`` cron job 的 ID 为 ``6fd93b4a4c4c``，每天北京时间 **04:00** 触发。

**Delegation（委托）**

编排器通过创建 kanban 任务将重活委托给子 agent。它本身从不运行抓取器——只是创建任务，由 kanban 调度器生成 ``scraper`` profile 的 worker 来执行。

组件架构
--------

下图展示所有 Hermes 组件及其关系：

.. mermaid::
   :caption: Hermes component architecture for music-daily-recs

   %%{init: { 'theme': 'default', 'themeVariables': { 'fontSize': '13px', 'primaryColor': '#e1e8f0', 'primaryTextColor': '#303030', 'primaryBorderColor': '#aaa' } } }%%
   graph TB
       CRON["cron_job<br/>6fd93b4a4c4c<br/>04:00 Beijing"]
       ORCH["orchestrator<br/>agent"]
       BB["kanban-batch-scrape.py<br/>~/.local/bin/"]
       DISP["kanban<br/>dispatcher"]
       SCRAPER_P["scraper<br/>profile"]
       ORCH_P["orchestrator<br/>profile"]
       SKILL["music-daily-recs<br/>skill"]
       SITES["sites.json<br/>~/.minimax/music-sites/"]

       CRON --> ORCH
       ORCH -.->|creates tasks| DISP
       ORCH --> BB
       ORCH --> SITES
       BB -->|creates| SCRAPER_T["43 × scraper tasks"]
       BB -->|creates| AGG_T["1 × aggregator task"]
       DISP -->|spawns| SCRAPER_W["scraper worker"]
       DISP -->|spawns| AGG_W["aggregator worker"]
       SCRAPER_W --> SCRAPER_P
       AGG_W --> SCRAPER_P
       ORCH -.->|loads| SKILL

       subgraph "Kanban Board"
           SCRAPER_T
           AGG_T
       end

       subgraph "music-record git repo"
           JSON["{site_id}_reviews.json"]
           AGG_JSON["aggregated.json<br/>filtered.json<br/>{DATE}.md"]
           REC_JSON["recommend/{DATE}.md"]
       end

       SCRAPER_T -->|writes| JSON
       JSON --> AGG_T
       AGG_T -->|writes| AGG_JSON
       AGG_T -->|writes| REC_JSON

串行-并行混合模式
-----------------

管线采用**父任务门控的串行-并行混合模式**，以调和两个相互冲突的约束：

**约束 A — 吞吐量：** 43 个抓取器必须尽快运行。
**约束 B — 资源：** 每个抓取器启动一个消耗约 200–400 MB RSS 的无头浏览器。同时运行全部 43 个会导致 OOM。

**解决方案：** ``batch_size = 2`` 的父任务门控分批。

批处理脚本每次创建两个任务为一组。只有*前一组的两个任务*都标记为 ``✓ done`` 后，下一组才开始调度。这意味着任意时刻只存在两个抓取器进程，而整体链路串行推进 22 个批次。

.. mermaid::
   :caption: 父任务门控 2 并发分批（简化示例，6 个站点）

   %%{init: { 'theme': 'default' } }%%
   graph LR
       B1["Batch 1<br/>scrape:A scrape:B<br/>no parent"]
       B2["Batch 2<br/>scrape:C scrape:D<br/>parents: A,B"]
       B3["Batch 3<br/>scrape:E scrape:F<br/>parents: C,D"]
       B4["Batch 4 …<br/>scrape:G scrape:H<br/>parents: E,F"]

       B1 --> B2
       B2 --> B3
       B3 --> B4

       style B1 fill:#c8e6c9
       style B2 fill:#fff9c4
       style B3 fill:#c8e6c9
       style B4 fill:#fff9c4

任务 Profile 分配
-----------------

43 个抓取任务和聚合任务共用同一个 ``scraper`` profile（相同认证、相同 workspace、相同 kanban-worker skill）。这是有意为之——聚合器可以直接从共享 workspace 读取抓取器的输出文件，无需任何跨进程传输机制。

唯一区分在于任务标题和 body 内容，它们将每个任务路由到单个 scraper worker 内部正确的站点专属或聚合逻辑。

**任务组分配：**

- **43 个抓取器** — assignee: ``scraper``，skills: ``kanban-worker``，workspace: ``dir:~/music-record/2026/{MM}/{DATE}/``
- **1 个聚合器** — assignee: ``scraper``，skills: ``kanban-worker``，workspace: 同上

目录结构
--------

git 仓库 ``pty819/music-record`` 是整个系统的中心存储：

::

   ~/music-record/                ← git 工作树
   ├── 2026/
   │   ├── 05/
   │   │   ├── 2026-05-12/       ← 以日期命名的子目录（workspace）
   │   │   │   ├── the_wire_reviews.json
   │   │   │   ├── point_of_departure_reviews.json
   │   │   │   ├── ...
   │   │   │   ├── 另外 43 个 {site_id}_reviews.json
   │   │   │   ├── aggregated.json
   │   │   │   ├── filtered.json
   │   │   │   └── 2026-05-12.md
   │   │   └── ...
   │   └── ...
   └── recommend/
       └── 2026-05-12.md         ← top-20 精选版
