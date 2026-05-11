Music Daily Recs — Pipeline Ebook
===================================

A comprehensive technical guide to the **music-daily-recs调研 pipeline**: an automated Hermes-based system that scans 43 music review sites every morning at 04:00 Beijing time, aggregates the results, scores them, and publishes a curated daily recommendation list.

.. toctree::
   :maxdepth: 3
   :numbered:

   chapter1_architecture
   chapter2_pipeline
   chapter3_dataflow
   chapter4_output

Introduction
------------

This ebook documents the architecture, data flow, concurrency model, and output behaviour of the music-daily-recs skill (``music-daily-recs``) running inside the Hermes task orchestration framework.

**What the pipeline does:**

1. A cron job fires at 04:00 Beijing time every day
2. A batch script creates 43 kanban tasks — two at a time, parent-gated — each running a site-specific scraper
3. Each scraper writes a ``{site_id}_reviews.json`` file to a date-labelled subdirectory in the ``music-record`` git repository
4. A final aggregator task reads all 43 JSON files, deduplicates them, scores each review, and writes three output files plus a git commit/push
5. A Telegram push delivers the top-20 recommendations to subscribers

**Key numbers:**

- **43** active music review sites (3 skipped: Boomkat, Syrphe, Textura — inaccessible)
- **43** scraper tasks + **1** aggregator task per run
- **2** scrapers running concurrently (parent-gated batching)
- **3** output files per run: ``aggregated.json``, ``filtered.json``, ``{DATE}.md``
- **1** top-20精简版: ``recommend/{DATE}.md``

.. mermaid::
   :caption: High-level pipeline overview

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
