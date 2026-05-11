Chapter 4 — Output Structure and Scoring Algorithm
=====================================================

This chapter documents the four output files produced each run, the scoring formula and its sub-components, and known biases in the current implementation.

4.1 Output Files
-----------------

For a run on ``2026-05-12``, the following files are written to the ``music-record`` repository:

**Primary output directory** — ``~/music-record/2026/05/2026-05-12/``:

``{site_id}_reviews.json`` (× 43)
    Raw output from each scraper. Format: JSON array of review objects. Files with no new articles contain an empty array. Files from ``crawl_strategy: "skip"`` sites are not created.

``aggregated.json``
    All unique reviews after deduplication. Contains every ``(album, artist)`` pair that appeared in any site's output, deduplicated by keeping the highest-scoring source entry.

``filtered.json``
    Subset of ``aggregated.json`` where ``total_score >= 6``. This is a historical accumulation file — it is *not* cleared between runs, so its size grows over time. Currently contains 1,700+ entries as of 2026-05-11.

``{DATE}.md`` — e.g. ``2026-05-12.md``
    Full markdown for the day. Contains every entry from ``filtered.json`` (all entries with score >= 6, no upper limit), formatted with full details. Each entry is prefixed with ``▸ [FEATURE]`` or ``▸ [TRACKLIST]`` as applicable.

**Top-20 output** — ``~/music-record/recommend/``:

``{DATE}.md`` — e.g. ``recommend/2026-05-12.md``
    The top-20精简版: the 20 highest-scoring entries from ``filtered.json``, each reduced to a single line. Format per entry: date, album, artist, score, source, one-line recommendation reason.

4.2 Review Type Classification
------------------------------

Before scoring, the aggregator classifies each review into one of three types:

``review``
    ``album`` field has content and ``artist`` field has content. No special markdown prefix.

``feature``
    ``album`` is empty/null, or matches a feature title pattern (e.g. "Spool's Out: ...", "Reissue of the Week: ...").
    Markdown prefix: ``▸ [FEATURE]``.

``tracklist``
    Source is ``the_wire`` and format is a tracklist entry.
    Markdown prefix: ``▸ [TRACKLIST]``.

**Classification priority:** tracklist (by source field) is checked first; then review vs feature (by album field content).

4.3 Scoring Formula
--------------------

Each review receives a ``total_score`` computed from six sub-scores:

.. code-block:: text

   total_score = (
       critic_quality(0-5)
     + taste_match(0-5)
     + novelty(0-3)
     + cross_domain_bonus(0-3)
     + regional_bonus(0-2)
     - mainstream_penalty(0-3)
   )

No hard cap exists — scores can theoretically exceed 15. In practice, most reviews score 6-12.

**Thresholds for output:**

- **Score >= 9:** Main recommendation — full markdown entry
- **6 <= score < 9:** Supplementary — also full markdown entry
- **score < 6:** Excluded from markdown; only present in JSON

4.4 Sub-Score Definitions
-------------------------

**critic_quality (0-5)**

- 5: Genuine music criticism with discussion of instrumentation, timbre, structure, cultural context
- 4: Substantive review with genre labels and descriptive language
- 3: Standard review with basic information
- 2: Brief news item, no body text
- 1: Title and one sentence only
- 0: Press release, announcement, ticket notice

**taste_match (0-5)**

- 5: Hits multiple taste dimensions simultaneously (e.g. free jazz + electroacoustic + world fusion)
- 4: Clearly within the core target: avant-garde / experimental / avant-jazz / academic electronic
- 3: Adjacent but peripheral
- 2: Marginally related
- 1: Barely relevant
- 0: Completely unrelated

**Synthwave/Darksynth/Dungeon Synth/Dark Ambient bonus (叠加到 taste_match 基础分):**

- synthwave (synthwave, retrowave): +1
- darksynth (darksynth, horror synth): +2
- dungeon synth / fantasy (dungeon synth, fantasy synth): +2
- dark ambient (dark ambient, ritual ambient): +2
- cinematic / soundtrack (soundtrack-inspired, cinematic synth): +1
- Berlin school / kosmische (berlin school, kosmische): +1

Cross-subcategory combinations (e.g. synthwave + darksynth, or dungeon synth + dark ambient) receive an additional +1.

**novelty (0-3)**

- 3: Entirely new concept, cross-cultural approach, unusual instrumentation, regional debut
- 2: Significant innovation present
- 1: Some novelty but not prominent
- 0: No novelty

Synthwave/Darksynth/Dungeon Synth/Dark Ambient novelty bonuses:

- synth/darksynth + world/folk/ritual elements: +2
- dungeon synth + modern sound design / field recording: +2
- Non-pure nostalgia imitation with clear expansion: +1
- Review emphasises "textural", "cinematic", "worldbuilding", "ritualistic", "atmospheric" with supporting detail: +1

**cross_domain_bonus (0-3)**

- 3: Spans 3 or more taste dimensions
- 2: Spans 2 dimensions
- 1: Spans 1 dimension
- 0: Single dimension

Synthwave/Darksynth/Dungeon Synth/Dark Ambient cross-domain bonuses:

- synthwave/darksynth + experimental electronic: +2
- darksynth + industrial / ritual / horror: +2
- dungeon synth + dark ambient: +2
- dungeon synth + folk / medieval / world: +2
- dark ambient + electroacoustic / sound art: +2
- synth + prog / fusion / jazz-rock: +2
- Spans three categories simultaneously: +1

**regional_bonus (0-2)**

- 2: Involves Southeast Asia, Austronesian, Central Asia, Latin America, Africa scenes
- 1: Has regional character but not central
- 0: Western mainstream

**mainstream_penalty (0-3)**

- 3: Pure pop, no experimental content
- 2: Has experimental tags but empty substance
- 1: Mainstream-leaning but has merit
- 0: Not mainstream-penalised

Synthwave/Retrowave/Dungeon Synth/Dark Ambient 降权:

- Synthwave/Retrowave: -1 if only 80s nostalgia aesthetic with no clear sound innovation; -1 if closer to a standard pop/synthpop single; -1 if review only says "fun", "nostalgic", "retro vibes"; -1 if pure neon cover + standard drum machine + conventional lead synth
- Dungeon Synth/Dark Ambient: -1 if just lo-fi pad stacks with no narrative/timbre design/world-building; -1 if pure tape-noise/lo-fi texture with no supporting detail; -1 if more like a demo/sketch/scene ephemera

4.5 Recommendation Reason Style
--------------------------------

The aggregator generates a one-line recommendation reason from the review excerpt. The style guide enforces specificity over vague praise:

**Good examples:**

- "把自由爵士管乐、粗粝电子纹理和近乎仪式性的打击循环缝在一起，张力非常足。"
- "在南岛/东南亚打击乐语感上叠加氛围电子与现场采样，既有地景感也有现代制作感。"
- "用 darksynth / horror-synth 的重型音色和明确的专辑结构把复古合成器语言推向更强的戏剧张力。"
- "不是单纯的 lo-fi fantasy 氛围堆叠，而是有明确场景感、叙事感和声音层次的 dark ambient / dungeon synth 作品。"

**Bad examples (too vague):**

- "很好听。"
- "很值得一听。"
- "很前卫。"
- "口碑不错。"

4.6 Known Issues and Biases
----------------------------

**Issue 1 — Songlines systematic inflation (confirmed 2026-05-11)**

In filtered.json, Songlines accounts for 88% of entries (1,513 out of 1,723). All top-20 entries on 2026-05-11 were from Songlines at 10.0 score.

Root cause (two layers):

1. ``filtered.json`` accumulates across runs without clearing — Songlines is one of the most consistently active sites, so it accumulates disproportionate weight
2. The scoring formula uses excerpt text to infer quality — Songlines is world-music-focused, which hits multiple taste dimensions and regional bonuses simultaneously, inflating its inferred scores

Fix direction: Clear ``filtered.json`` each run (snapshot, not accumulation); prefer native site scores where available; cap per-source entries in top-20.

**Issue 2 — Aggregator parent-gating occasionally fails**

Phenomenon: All 43 scrapers show ``✓ done``, but aggregator stays ``◻ todo`` and never auto-dispatches.

Root cause: The batch script creates a new aggregator with ``parents=all_task_ids`` each run. If a previous run's aggregator is still on the board (not archived), its parents may point to archived task IDs. The dispatcher sees "parents not done" and never dispatches.

Recovery: Archive the stuck aggregator; use fallback aggregation script; do not recreate a new aggregator (same parent-ID problem recurs).

**Issue 3 — Telegram push tied to aggregator body**

The Telegram top-20 push is embedded in the aggregator task's ``body`` instruction, not a separate task. If the aggregator crashes or is blocked, Telegram push is silently skipped.

**Issue 4 — The Wire permanently inaccessible**

- ``/category/reviews`` returns 404
- RSS returns HTML instead of XML
- Web search finds no useful reviews

Result: ``status: "paywalled"`` set in sites.json, site excluded from scraper runs permanently.

**Issue 5 — Fluid Radio is an archive, not a live feed**

RSS returns 671 historical entries from 2013-2022. The site may be defunct. Handled by marking ``crawl_strategy: "skip"`` and drawing 2-3 random archive entries per run.

.. mermaid::
   :caption: Scoring data flow — from excerpt to recommendation

   %%{init: { 'theme': 'default' } }%%
   flowchart TB
       EX["Review excerpt<br/>+ metadata<br/>(album, artist, tags,<br/>source, pub_date)"]
       EX --> T1["critic_quality<br/>0-5"]
       EX --> T2["taste_match<br/>0-5 + bonuses"]
       EX --> T3["novelty<br/>0-3 + bonuses"]
       EX --> T4["cross_domain<br/>0-3 + bonuses"]
       EX --> T5["regional<br/>0-2"]
       EX --> T6["mainstream<br/>0 to -3"]

       T1 & T2 & T3 & T4 & T5 & T6 --> SUM["total_score"]
       SUM --> G9["score >= 9<br/>Main rec"]
       SUM --> G6["6 <= score < 9<br/>Supplementary"]
       SUM --> L6["score < 6<br/>JSON only"]

       G9 & G6 --> MD["{DATE}.md<br/>(all >= 6)"]
       G9 & G6 --> FILT["filtered.json<br/>(all >= 6)"]
       G9 & G6 --> TOP20["Top 20 by score<br/>recommend/{DATE}.md"]
       L6 --> AGG["aggregated.json<br/>(all unique)"]

       MD & FILT & TOP20 & AGG --> PUSH["git push<br/>music-record"]

       style SUM fill:#fff9c4,stroke:#f59e0b
       style G9 fill:#c8e6c9
       style G6 fill:#c8e6c9
       style L6 fill:#ffebee
       style TOP20 fill:#e8f5e9
