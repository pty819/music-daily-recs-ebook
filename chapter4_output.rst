输出结构与评分算法
==================

本章记录每次运行产生的四个输出文件、评分公式及其子项，以及当前实现中的已知偏差。

输出文件
--------

以 ``2026-05-12`` 的运行为例，以下文件被写入 ``music-record`` 仓库：

**主要输出目录** — ``~/music-record/2026/05/2026-05-12/``：

``{site_id}_reviews.json``（× 43）
    每个抓取器的原始输出。格式：review 对象的 JSON 数组。没有新文章的文件的数组为空。``crawl_strategy: "skip"`` 站点的文件不会被创建。

``aggregated.json``
    去重后的所有唯一评论。包含所有出现在任意站点输出中的 ``(album, artist)`` 对，以保留得分最高来源条目为原则去重。

``filtered.json``
    ``aggregated.json`` 的子集，条件为 ``total_score >= 6``。这是历史累积文件——两次运行之间**不会清空**，所以大小随时间增长。截至 2026-05-11 已有 1700+ 条目。

``{DATE}.md`` — 例如 ``2026-05-12.md``
    当日的完整 markdown。包含 ``filtered.json`` 中每个条目（得分 ≥ 6，无上限），格式为完整详情。每个条目根据类型前缀 ``▸ [FEATURE]`` 或 ``▸ [TRACKLIST]``。

**Top-20 输出** — ``~/music-record/recommend/``：

``{DATE}.md`` — 例如 ``recommend/2026-05-12.md``
    Top-20 精选版：从 ``filtered.json`` 中取得分最高的 20 条，每条缩减为一行。格式：日期、专辑名、艺术家、得分、来源、一句话推荐理由。

评论类型分类
------------

评分之前，聚合器将每条评论分为三个类型之一：

``review``
    ``album`` 字段和 ``artist`` 字段都有内容。无特殊 markdown 前缀。

``feature``
    ``album`` 字段为空/null，或匹配特辑标题模式（如 "Spool's Out: ..."、"Reissue of the Week: ..."）。
    Markdown 前缀：``▸ [FEATURE]``。

``tracklist``
    来源为 ``the_wire`` 且格式为曲目列表条目。
    Markdown 前缀：``▸ [TRACKLIST]``。

**分类优先级：** 先按来源字段检查 tracklist；再按 album 字段内容区分 review 和 feature。

评分公式
--------

每条评论获得一个由六个子分构成的 ``total_score``：

.. code-block:: text

   total_score = (
       critic_quality(0-5)
     + taste_match(0-5)
     + novelty(0-3)
     + cross_domain_bonus(0-3)
     + regional_bonus(0-2)
     - mainstream_penalty(0-3)
   )

没有硬性上限——得分理论上可以超过 15。实际上大多数评论得分在 6-12 之间。

**输出阈值：**

- **得分 >= 9：** 主推——完整 markdown 条目
- **6 <= 得分 < 9：** 补充——同样写入完整 markdown 条目
- **得分 < 6：** 不写入 markdown；仅存在于 JSON

子分定义
--------

**critic_quality（0-5）**

- 5：真正的音乐评论，讨论了配器、音色、结构、文化背景
- 4：有实质内容的评论，有风格标签和描述性语言
- 3：标准评论，提供基本信息
- 2：简短新闻，无正文
- 1：标题加一句话
- 0：新闻稿、公告、票务通知

**taste_match（0-5）**

- 5：同时命中多个品味维度（如自由爵士 + 电声 + 世界融合）
- 4：明显属于核心目标：前卫/实验/先锋爵士/学院派电子
- 3：相邻但边缘
- 2：勉强相关
- 1：几乎无关
- 0：完全无关

**Synthwave/Darksynth/Dungeon Synth/Dark Ambient 加分（叠加到 taste_match 基础分）：**

- synthwave（synthwave、retrowave）: +1
- darksynth（darksynth、horror synth）: +2
- dungeon synth / fantasy（dungeon synth、fantasy synth）: +2
- dark ambient（dark ambient、ritual ambient）: +2
- cinematic / soundtrack（soundtrack-inspired、cinematic synth）: +1
- Berlin school / kosmische（berlin school、kosmische）: +1

跨子类别组合（如 synthwave + darksynth，或 dungeon synth + dark ambient）额外 +1。

**novelty（0-3）**

- 3：全新概念、跨文化视角、非寻常配器、地区首发
- 2：有显著创新
- 1：有新意但不突出
- 0：无新意

Synthwave/Darksynth/Dungeon Synth/Dark Ambient novelty 加分：

- synth/darksynth + world/folk/ritual 元素: +2
- dungeon synth + 现代声音设计/田野录音: +2
- 非纯怀旧模仿、有明确扩展: +1
- 评论强调"质感"、"电影感"、"世界构建"、"仪式感"、"氛围"且有细节支撑: +1

**cross_domain_bonus（0-3）**

- 3：跨越 3 个或以上品味维度
- 2：跨越 2 个维度
- 1：跨越 1 个维度
- 0：单一维度

Synthwave/Darksynth/Dungeon Synth/Dark Ambient 跨域加分：

- synthwave/darksynth + 实验电子: +2
- darksynth + industrial / ritual / horror: +2
- dungeon synth + dark ambient: +2
- dungeon synth + folk / medieval / world: +2
- dark ambient + 电声/声音艺术: +2
- synth + prog / fusion / jazz-rock: +2
- 同时跨越三个类别: +1

**regional_bonus（0-2）**

- 2：涉及东南亚、南岛、中亚、拉丁美洲、非洲场景
- 1：有地区特色但非核心
- 0：西方主流

**mainstream_penalty（0-3）**

- 3：纯流行，无实验内容
- 2：有实验标签但内容空洞
- 1：偏主流但有价值
- 0：未受主流惩罚

Synthwave/Retrowave/Dungeon Synth/Dark Ambient 降权：

- Synthwave/Retrowave: 若仅有 80 年代怀旧美学无明显声音创新 -1；若更接近标准流行/synthpop 单曲 -1；若评论只说"好玩"、"怀旧"、"复古氛围" -1；若纯霓虹封面 + 标准鼓机 + 常规主音合成器 -1
- Dungeon Synth/Dark Ambient: 若只是 lo-fi 音色垫堆无叙事/音色设计/世界构建 -1；若纯磁带噪音/lo-fi 纹理无细节支撑 -1；若更像 demo/草稿/场景 ephemera -1

推荐理由风格
------------

聚合器从评论摘要生成一行推荐理由。风格指南要求具体、反对空泛：

**好例子：**

- "把自由爵士管乐、粗粝电子纹理和近乎仪式性的打击循环缝在一起，张力非常足。"
- "在南岛/东南亚打击乐语感上叠加氛围电子与现场采样，既有地景感也有现代制作感。"
- "用 darksynth / horror-synth 的重型音色和明确的专辑结构把复古合成器语言推向更强的戏剧张力。"
- "不是单纯的 lo-fi fantasy 氛围堆叠，而是有明确场景感、叙事感和声音层次的 dark ambient / dungeon synth 作品。"

**坏例子（太模糊）：**

- "很好听。"
- "很值得一听。"
- "很前卫。"
- "口碑不错。"

已知问题与偏差
--------------

**问题 1 — Songlines 系统性得分膨胀（2026-05-11 确认）**

在 filtered.json 中，Songlines 占 88%（1513/1723 条）。2026-05-11 的所有 top-20 条目均来自 Songlines，得分 10.0。

根本原因（两层）：

1. ``filtered.json`` 跨运行累积不清理——Songlines 是最持续活跃的站点之一，权重不成比例地累积
2. 评分公式用摘要文本来推断质量——Songlines 专注世界音乐，同时命中多个品味维度和地区加分，推高推断得分

修复方向：每次运行清空 ``filtered.json``（做快照而非累积）；优先使用站点原生分数；限制 top-20 中每个来源的条目数上限。

**问题 2 — 聚合器父任务门控偶发失败**

现象：43 个抓取器全部显示 ``✓ done``，但聚合器保持 ``◻ todo`` 不自动分发。

根本原因：批处理脚本每次运行都会创建一个以 ``parents=all_task_ids`` 新聚合器。若上次运行的聚合器仍在看板上（未归档），它的父任务可能指向已归档的任务 ID。调度器看到"父任务未完成"就不分发。

恢复方案：归档卡住的聚合器；使用备用聚合脚本；不要重建新聚合器（同样会复发父任务 ID 问题）。

**问题 3 — Telegram 推送与聚合器 body 绑定**

Telegram top-20 推送嵌入在聚合器任务的 ``body`` 指令中，而非独立任务。若聚合器崩溃或被阻塞，Telegram 推送会被静默跳过。

**问题 4 — The Wire 永久不可访问**

- ``/category/reviews`` 返回 404
- RSS 返回 HTML 而非 XML
- Web 搜索找不到有用的评论

结果：在 sites.json 中设置 ``status: "paywalled"``，永久排除在抓取运行之外。

**问题 5 — Fluid Radio 是档案而非实时源**

RSS 返回 671 条 2013-2022 年的历史条目。网站可能已停用。处理方式：标记 ``crawl_strategy: "skip"``，每次运行从档案中随机抽取 2–3 条。

.. mermaid::
   :caption: 评分数据流——从摘要到推荐

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
