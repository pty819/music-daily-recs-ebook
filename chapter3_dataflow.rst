Chapter 3 — Data Flow and Transformation
========================================

This chapter describes how data moves through the pipeline from raw HTTP responses to final JSON and Markdown files.

3.1 Site Categories
--------------------

The 43 active sites fall into three groups based on content update frequency and technical accessibility:

**RSS-first group (~21 sites):**
Sites with working RSS feeds. The scraper uses ``curl + feedparser`` — fastest path, lowest resource usage. Only articles published within the last 7 days are included; older entries are discarded and pagination stops immediately.

**Playwright group (~22 sites):**
No reliable RSS, or RSS returns historical archives (e.g. Fluid Radio — 671 historical entries from 2013–2022). The scraper launches a headless Chromium browser (``browser_navigate``) with stealth mode, visits the review listing page, and scrapes the first 2 list pages maximum. If all items on page 1 are older than 7 days, page 2 is never visited.

**Search fallback group:**
Paywalled sites (e.g. The Wire) or sites blocked by Cloudflare JS challenges. The scraper degrades to ``web_search`` with the same 7-day window constraint.

**Special case — Fluid Radio:**
The site's RSS returns exclusively 2013–2022 archive content. It is marked ``crawl_strategy: "skip"`` in sites.json and excluded from normal scraping. The aggregator instead performs a random draw of 2–3 entries from the archive on each run, tagged ``[Fluid Radio Archive]``, to keep the archive content slowly cycling into recommendations.

3.2 Scraper Output Format
--------------------------

Every scraper writes a single JSON file named ``{site_id}_reviews.json`` to the workspace directory.

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

If the site returns no new articles, the file contains an empty array:

.. code-block:: json

   { "site_id": "boomkat", "reviews": [], "crawl_status": "no_new_articles" }

3.3 Serial-Parallel Hybrid Diagram
-----------------------------------

The diagram below shows the full parent-gating chain for 6 sites (BATCH_SIZE=2). The same pattern repeats for all 43 sites across 22 batches.

.. mermaid::
   :caption: Full parent-gating chain — 6 sites shown (BATCH_SIZE=2)

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

3.4 Data Transformation Pipeline
----------------------------------

The aggregator performs four distinct transformations on the raw scraper output:

.. mermaid::
   :caption: Data transformation inside the aggregator

   %%{init: { 'theme': 'default' } }%%
   flowchart LR
       subgraph "1. Collect & Merge"
           J1["{site1}_reviews.json"]
           J2["{site2}_reviews.json"]
           J3["{site3}_reviews.json"]
           JN["… × 43"]
           J1 & J2 & J3 & JN --> MERGE["Concatenated list<br/>N total entries"]
       end

       subgraph "2. Deduplicate"
           MERGE --> DEDUP["Dedupe by<br/>(album + artist) key<br/>keep highest score"]
           DEDUP --> UNIQ["U unique entries<br/>U ≤ N"]
       end

       subgraph "3. Score & Classify"
           UNIQ --> CLASS["Classify: review / feature / tracklist"]
           CLASS --> SCORE["Apply scoring formula<br/>Compute total_score"]
           SCORE --> FILTER["Split by score"]
       end

       subgraph "4. Render & Persist"
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

3.5 Git Push Flow
-----------------

After writing the four output files, the aggregator executes a git commit and push inside the ``music-record`` repository:

.. code-block:: bash

   cd ~/music-record

   git add \
     2026/05/2026-05-12/aggregated.json \
     2026/05/2026-05-12/filtered.json \
     2026/05/2026-05-12/2026-05-12.md \
     recommend/2026-05-12.md

   git commit -m "auto: 2026-05-12 daily recs"
   git push origin main

The workspace directory is the date-named subdirectory within the git working tree, so all file paths are relative to ``~/music-record`` and the push immediately updates the shared repository.

.. mermaid::
   :caption: Git push flow

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
