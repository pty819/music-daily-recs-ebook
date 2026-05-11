Chapter 1 — Hermes Architecture Overview
========================================

The music-daily-recs skill runs inside **Hermes**, a task orchestration framework built around the concept of a **kanban board** with intelligent agents, cron triggers, skill loaders, and delegation.

1.1 Core Concepts
-----------------

Agents
~~~~~~

An **agent** is a named execution context with its own identity, auth credentials, and tool access. The pipeline uses two agent profiles:

- ``orchestrator`` — the cron agent that owns the daily pipeline run: it cleans stale tasks, syncs ``sites.json``, calls the batch script, and pushes Telegram
- ``scraper`` — the profile used for all 43 site-specific scraper tasks and the final aggregator task; it carries the shared ``auth.json`` (single ``minimax-cn`` provider) and the kanban worker skill

Skills
~~~~~~

A **skill** is a YAML/JSON document stored under ``~/.hermes/skills/`` that defines what an agent can do. The ``music-daily-recs`` skill describes the full pipeline as a sequence of steps (积压清理 → sync sites → batch create → monitor → Telegram push). Skills are loaded into the agent context at dispatch time.

Kanban
~~~~~~

The **kanban board** is Hermes's task queue. Each task has:

- ``id`` — unique task identifier
- ``title`` — human-readable label
- ``body`` — full instruction text (passed to the agent's LLM)
- ``assignee`` — which agent profile runs it
- ``parents`` — list of task IDs that must complete before this one is dispatched
- ``children`` — auto-derived: tasks that list this one as parent
- ``status`` — ``◻ todo``, ``▶ ready``, ``✓ done``, ``⊘ blocked``
- ``skills`` — required skill tags for dispatch routing
- ``workspace`` — working directory for file I/O

Cron
~~~~

Hermes cron jobs (``cron_job`` in skill metadata) are scheduled triggers that fire a prompt into an agent session at a fixed wall-clock time. The ``music-daily-recs`` cron job has ID ``6fd93b4a4c4c`` and fires at **04:00 Beijing time (UTC+8)** every day.

Delegation
~~~~~~~~~~

The orchestrator **delegates** heavy work to sub-agents by creating kanban tasks. It never runs the scrapers itself — it creates the tasks and the kanban dispatcher spawns ``scraper`` profile workers to execute them.

1.2 Component Architecture
---------------------------

The diagram below shows all Hermes components and their relationships:

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

1.3 The Serial-Parallel Hybrid Pattern
---------------------------------------

The pipeline uses a **parent-gated serial-parallel hybrid** to reconcile two competing constraints:

**Constraint A — Throughput:** 43 scrapers must run as fast as possible.
**Constraint B — Resource:** Each scraper launches a headless browser consuming ~200–400 MB RSS. Running all 43 simultaneously causes OOM.

**Solution:** parent-gated batching with ``batch_size = 2``.

The batch script creates tasks in groups of two. Each group does not start until the *previous* group's two tasks are marked ``✓ done``. This means only two scraper processes exist at any moment, while the overall chain progresses serially through 22 batches.

.. mermaid::
   :caption: Parent-gated 2-concurrent batching (simplified, 6 sites shown)

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

1.4 Task Profile Assignment
----------------------------

All 43 scraper tasks and the aggregator task share the same ``scraper`` profile (same auth, same workspace, same kanban-worker skill). This is intentional — it allows the aggregator to read the scrapers' output files directly from the shared workspace without any inter-process transfer mechanism.

The only distinction is task title and body content, which route each task to the correct site-specific or aggregation logic inside the single scraper worker.

**Task group assignments:**

- **43 scrapers** — assignee: ``scraper``, skills: ``kanban-worker``, workspace: ``dir:~/music-record/2026/{MM}/{DATE}/``
- **1 aggregator** — assignee: ``scraper``, skills: ``kanban-worker``, workspace: same dir

1.5 Directory Layout
--------------------

The git repository ``pty819/music-record`` is the central store:

::

   ~/music-record/                ← git working tree
   ├── 2026/
   │   ├── 05/
   │   │   ├── 2026-05-12/       ← date-named subdirectory (workspace)
   │   │   │   ├── the_wire_reviews.json
   │   │   │   ├── point_of_ departure_reviews.json
   │   │   │   ├── ...
   │   │   │   ├── 43 more {site_id}_reviews.json
   │   │   │   ├── aggregated.json
   │   │   │   ├── filtered.json
   │   │   │   └── 2026-05-12.md
   │   │   └── ...
   │   └── ...
   └── recommend/
       └── 2026-05-12.md         ← top-20精简版
