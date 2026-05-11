Chapter 2 — The Full Pipeline
=============================

This chapter traces a single daily run from cron trigger to git push.

2.1 Trigger: Cron at 04:00 Beijing Time
----------------------------------------

The ``music-daily-recs`` skill declares a cron job with ID ``6fd93b4a4c4c``:

.. code-block:: yaml

   cron_job: 6fd93b4a4c4c（每天 04:00 北京时间自动运行 pipeline + git push）

When the cron fires, Hermes creates a new agent session for the ``orchestrator`` profile, loads the ``music-daily-recs`` skill, and injects the full pipeline prompt as the session message. The orchestrator then executes the steps sequentially — it never delegates to sub-agents for the orchestration logic itself.

Beijing time 04:00 is deliberately early morning: most music review sites update their content overnight (US/EU time zones), so by 04:00 Beijing the previous day's reviews are fully published.

2.2 Step 0 — Backlog Cleanup (Always First)
--------------------------------------------

Before anything else, the orchestrator must clear stale ``◻ todo`` scraper tasks from previous runs:

.. code-block:: bash

   hermes kanban list | grep "◻" | grep "scrape:" | awk '{print $2}' | while read id; do
     hermes kanban archive "$id"
   done

Without this step, the board accumulates 43+ stale tasks per run. After three days, 120+ ghost tasks would be visible, and the dispatcher could get confused about parent relationships.

The orchestrator also verifies ``auth.json`` at this point — confirming only the ``minimax-cn`` provider is present and the scraper profile config points to ``minimax-cn``.

2.3 Step 1 — Sync sites.json
----------------------------

The orchestrator pulls the latest site configuration from the ``music-record`` git repository:

.. code-block:: bash

   cd ~/.minimax/music-sites && git pull origin main

The file ``~/.minimax/music-sites/sites.json`` defines all 46 configured sites:

- **43 active** — ``crawl_strategy`` is ``rss`` or ``playwright_headless``
- **3 skipped** — Boomkat, Syrphe, Textura (``crawl_strategy: "skip"`` — inaccessible)

Sites that return paywalled responses get ``status: "paywalled"`` set in the JSON (e.g. The Wire) and are not retried.

2.4 Step 2 — Batch Script Execution
-------------------------------------

This is the critical step where the 43 scraper tasks are created correctly.

**⚠️ The wrong approach:** looping ``kanban create`` 43 times without parent gating.
This spawns 43 concurrent headless browsers → OOM crash.

**✅ The correct approach:** ``kanban-batch-scrape.py``.

.. code-block:: bash

   python3 ~/.local/bin/kanban-batch-scrape.py --confirm

Inside the script (simplified logic):

.. code-block:: python

   BATCH_SIZE = 2
   batches = [sites[i:i+BATCH_SIZE] for i in range(0, len(sites), BATCH_SIZE)]

   prev_task_ids = []
   for batch_idx, batch in enumerate(batches):
       parents = list(prev_task_ids)  # empty for first batch

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

The first batch has **no parents** — both tasks dispatch immediately.
The second batch sets ``parents=[t1a, t1b]`` — dispatcher waits until both are ``✓ done``.
The third batch sets ``parents=[t2a, t2b]``, and so on.

After all 43 scraper tasks are created, the script creates the **aggregator task** with ``parents=all_task_ids`` — it will not dispatch until every scraper is done.

Result after ``--confirm``:

- **22 batches × 2 = 44** task creations, but only 43 scrapers (one batch has only 1 site)
- **1 aggregator** with 43 parent dependencies

2.5 Step 3 — Scraper Execution
-------------------------------

Each scraper task runs inside a ``scraper`` profile worker. The worker's LLM reads the task ``body`` and executes the scraping instructions. The task body is the same template for all sites; site-specific parameters (URL, strategy, tags) are injected via string interpolation.

**Scraping strategies:**

**Scraping strategies:**

- ``rss`` — ``curl + feedparser``, parse XML, filter last 7 days
- ``playwright_headless`` — ``browser_navigate`` headless + stealth, 2 pages max
- ``search_fallback`` — ``web_search`` (paywall/cloudflare degraded)

For all strategies, **7-day window is enforced**: articles older than 7 days are skipped, and pagination stops immediately upon hitting the first stale article.

Sites with **no new articles** return an empty JSON array ``[]`` — this is correct behaviour, not an error.

Output per scraper: a single file ``{site_id}_reviews.json`` written directly to the workspace directory (which is the date subdirectory inside the git repo):

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

The scraper then calls ``kanban_complete(summary="scraped N reviews from {name} (last 7 days)", metadata={...})``.

2.6 Step 4 — Aggregator Execution
-----------------------------------

The aggregator task does not dispatch until all 43 scraper ``parents`` are ``✓ done``. It runs in the same ``scraper`` profile (same auth, same worker skill) and reads the shared workspace directory.

**Aggregator steps:**

1. **Collect** — reads all ``*_reviews.json`` files from the workspace
2. **Merge** — concatenates all JSON arrays into one list
3. **Deduplicate** — ``(album + artist)`` key; if duplicate found, keep the higher-scoring source
4. **Classify** — assigns ``type``: ``review`` (has album + artist), ``feature`` (has artist but no album, or album is a feature title like "Reissue of the Week"), or ``tracklist`` (from The Wire)
5. **Score** — applies the scoring formula (see Chapter 4)
6. **Filter** — splits into ``aggregated.json`` (all unique reviews) and ``filtered.json`` (score ≥ 6)
7. **Render markdown** — writes ``{DATE}.md`` (full list, score ≥ 6) and ``recommend/{DATE}.md`` (top 20, score ≥ 6, highest scores first)
8. **Git push** — commits and pushes all four files to ``pty819/music-record``
9. **kanban_complete** — signals done

2.7 Step 5 — Telegram Push
----------------------------

The orchestrator reads the ``recommend/{DATE}.md`` file and sends the top-20 entries to the Telegram channel. This is the last step of the cron job prompt.

**Known issue:** if the aggregator task crashes (parent-gating bug), the Telegram push is also skipped, because it is currently embedded in the aggregator task body rather than being a separate task.

.. mermaid::
   :caption: End-to-end pipeline flow

   %%{init: { 'theme': 'default' } }%%
   flowchart TB
       subgraph "Orchestrator (cron agent)"
           A0["Step 0<br/>Archive stale tasks"]
           A1["Step 1<br/>git pull sites.json"]
           A2["Step 2<br/>kanban-batch-scrape.py"]
           A3["Step 4<br/>Monitor scrapers"]
           A4["Step 5<br/>Push Telegram top-20"]
           A0 --> A1 --> A2 --> A3 --> A4
       end

       subgraph "Scraper profile workers (2 concurrent)"
           S1["Batch 1 scrapers"]
           S2["Batch 2 scrapers"]
           SN["Batch N scrapers"]
           S1 --> S2 --> SN
       end

       subgraph "Aggregator (scraper profile)"
           AGG["Read all JSON → Dedup → Score → Write files → Git push"]
       end

       A2 -->|"creates 43 tasks<br/>+ 1 aggregator"| S1
       SN -->|"all 43 done<br/>parent unblocked"| AGG
