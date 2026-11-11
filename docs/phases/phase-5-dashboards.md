# Phase 5: Power BI dashboards on a public web page

**Goal:** a Power BI report on the gold star schema, with four pages (skills overview, rising skills, salaries, skills asked together), refreshed every night after the pipeline and embedded with Publish to web in a GitHub Pages site. The report shows aggregates only, and Himalayas keeps its place in the weekly trend after its jobs expire.

**Done when:**
- The PBIP project in `dashboards/` opens in Power BI Desktop, refreshes from Databricks, and its counts match gold.
- The four pages work with filters for region and country, industry, seniority, job type and date, starting on jobs listed now. Every page credits the sources.
- The weekly trend covers all three sources. Himalayas weeks are frozen as counts before their jobs expire.
- The published report refreshes daily at 19:00 UTC, and https://robi4419.github.io/Nexus-Project/ shows it to anyone, with no sign-in.
- The repository is public, after its fixtures were made up and its history checked for secrets.
- `pytest` and `dbt build` pass.

## Progress
- [x] 5.1 Branch, plan doc, `PLAN.md`
- [x] 5.2 Himalayas history: frozen daily counts in dbt, and a weekly trend for all three sources
- [x] 5.3 You: Power BI Desktop, a Databricks token for Power BI, and an empty PBIP project in `dashboards/`
- [x] 5.4 Semantic model in TMDL: tables, relationships, hierarchies, DAX measures; refreshed and checked against gold
- [x] 5.5 Report pages (you build them, I guide): skills overview, rising skills, salaries, skills asked together
- [x] 5.6 Account and publishing: tenant, Pro trial, Publish to web, daily refresh
- [x] 5.7 Make the repository public: made-up fixtures, history scan, author email, licence
- [ ] 5.8 GitHub Pages site with the iframe
- [x] 5.9 Verify end to end
- [x] 5.10 Docs, commit, PR and merge (PR #8, merged on 2026-11-05)
- [ ] 5.11 Board weights in the weekly trend (decision 14), on the branch `trend-board-weights`

---

## Starting point (2026-11-01)

| Area | State |
|---|---|
| Gold | `workspace.gold`: 6 dimensions, `fct_job_postings` (34,764 jobs), `fct_job_skills` (186,618 rows), 3 bridges, `agg_skill_co_occurrence`, `agg_skill_weekly_trend` (Jobicy and Arbeitnow only, Phase 3 decision 3), rebuilt every night by `transform_and_build` |
| Himalayas jobs | 18,118 in silver, first seen in the weeks of 19 and 26 October; deleted at `expiryDate` (Phase 2b, decision 18). The oldest expire around 18 December |
| Power BI | Nothing yet. Desktop is free; the service needs a work account (Gmail isn't accepted) |
| Repository | Private; `dashboards/` holds only a `.gitkeep` |

## Decisions (2026-10-30 and 2026-11-01)

1. **Publish to web, from the Power BI service.** Free licences can't create embed codes (Microsoft Learn, September 2026), so:
   - your own tenant comes from a Microsoft 365 trial, and you keep the `…onmicrosoft.com` account after cancelling it;
   - a 60-day Pro trial covers publishing; before it ends, you decide between Pro (about $14 a month) and screenshots.

   Rejected:
   - Power BI Embedded: paid capacity plus server code to issue tokens;
   - secure embedding: every viewer would need a licence.
2. **The page is on GitHub Pages, from this repository, which becomes public.** GitHub's free plan serves Pages only from public repositories. Rejected: a separate public repo; GitHub Pro.
3. **The report shows aggregates only.** The model keeps one row per job for filtering and counting, with no titles, links, source IDs, descriptions or raw salary fields. It also leaves out companies, which no page needs. Publish to web lets anyone read the whole model, so what isn't imported can't leak. Expired Himalayas jobs leave the model with each nightly refresh.
4. **Himalayas' weekly history is kept as counts that never shrink.**
   - **The terms:** clause 113(d) says "Cache job data where you can … and remove jobs once they expire." That rule is about stored jobs, so the purges stay. The terms don't mention aggregated data at all, and a count holds no job. This is our reading of terms that say nothing on the point; an email to hi@himalayas.app would make it certain.
   - **Two incremental dbt models** store counts of Himalayas jobs per day first seen, and per day first seen × skill. Each nightly build appends only the jobs first seen since the previous build, so every job is counted once, before it can expire.
   - **The watermark is the latest `first_seen_at` already counted, not a date,** so a rerun on the same day adds only what's new.
   - **`full_refresh: false`** stops a full rebuild from wiping the history. The first build backfills every Himalayas job still in silver.
   - **Why per day and not per week:** 18 of 18,118 Himalayas jobs (0.1%) expire within 7 days of being first seen. A weekly freeze would lose them.
5. **The weekly trend covers all three sources, one row per week × skill × source.**
   - Jobicy and Arbeitnow are counted by publish week, from silver as now.
   - Himalayas is counted by the week each job was first seen, from the frozen counts. Its `pubDate` is the last update, so counting by it would move refreshed jobs to later weeks.
   - DAX measures compute shares and week-over-week changes, so any choice of sources works.
   - The title fallback (Phase 4, decision 8) changes Himalayas' mix from 2026-10-31. The page notes it, and a source slicer can leave Himalayas out.
   - *Changed by decision 12:* one row per week × skill, each job once, and no source slicer.
6. **I write the semantic model, and you build the visuals.** The model is TMDL text in the PBIP project: tables, Databricks queries, relationships, hierarchies and measures, reviewable in git. You build the pages in Desktop with my step-by-step guidance. Everything is committed, except Desktop's local cache and settings.
7. **Four pages, each with a credits footer, starting on jobs listed now:**
   - **Skills overview:** top skills and categories by share of jobs, with filters for region and country, industry, seniority, job type and date.
   - **Rising skills:** biggest risers and fallers week over week, and a trend line per skill.
   - **Salaries:** median yearly salary in USD by skill, seniority and region, using plausible salaries only; also the share of jobs listing a salary.
   - **Skills asked together:** a co-occurrence heatmap, and "often asked with X" ranked by lift.

   The overview and salary pages start filtered on `is_listed_now`, and a slicer includes the rest. The two `agg_` tables ignore the dashboard filters by design (Phase 3).
8. **The Databricks host and HTTP path are two Power Query parameters, committed with the model.** They aren't credentials: the token is never in the project files, because Desktop and the service store credentials separately. A new token named `power-bi` can be revoked without touching dbt's.
9. **The published model refreshes daily at 19:00 UTC,** after the nightly chain (green by about 18:30), with refresh-failure emails on.
10. **(2026-11-03) Skills come only from the description's lines about the job.**
    - **Why:** DocuSign ranked among the best-paid skills, but two-thirds of its 80 jobs only named it in the employer's text. 33 were Oura's and Adastra's "offers are sent through DocuSign" notice, and 20 were customer lists such as Mirantis' "serves … Adobe, DocuSign, … Splunk". The same text inflated other skills: Stripe (startups "like Stripe" in About text), Lever (French "lever des fonds"), Apache Spark (the investor Spark Capital), GDPR (applicant-privacy notices), and Go (German "das Go geben").
    - **The rule** is `job_text()` in `transform/skills.py`. Each line belongs to the section its last heading opened.
      - **Headings** are recognised from lists of job headings (requirements, responsibilities, nice to have, the role… or a heading naming the job's title) and company headings (about us, benefits, privacy, interview process, the boards' footers), in English, German, French, Dutch, Spanish and Portuguese.
      - **Job sections** count whole, and so do sections under an unknown heading.
      - **Notices** never count outside job sections: customer and investor lists, offer notices and applicant-privacy text.
      - **Company sections** count only requirement-like lines (*experience*, *you*, *du*, *vous*, *je*…).
      - **Lines before the first heading** count only when they read like a requirement, unless the posting has no job section; then they all count.
      - **The title** always counts.
    - **Measured on 3,604 jobs** (one in twelve, 2026-11-03), against whole-text matching:
      - 2.9% of skill tags dropped, nearly all the employer's own text;
      - Python lost about 1% of its tags; Notion 37%, Canva 32%, Stripe 26%, GDPR 24%.
    - **Rejected:**
      - Counting only job sections: it dropped 7.1% of tags, including real requirements written before the first heading or under unrecognised headings.
      - Dropping sentences a company repeats across its roles: it would need company-level aggregation in Spark for little extra.
    - **Not filtered, after checking:**
      - negations: 228 lines in 44,179 postings, mostly "a bonus, not a requirement", which are real nice-to-haves;
      - English skill names in other languages' prose: the top matches were genuine.
    - **With it:** the HTML fix in `transform/text.py` (Phase 2, section 2.6). 16% of Arbeitnow descriptions had their HTML left as visible tags on one long line, so they had no headings for this rule to find.
    - **History:** the Himalayas history was rebuilt once for decision 11, after this rule was deployed, so every week of the trend uses it.
    - **In production (2026-11-03):** silver's posting skill tags fell from 237,790 to 231,414 (−2.7%).
11. **(2026-11-03) A job counts once, however often it's posted.**
    - **Why:** 3,795 of 31,647 listed postings (12%) repeated a job already counted, so a few companies' requirements weighed several times in every share:
      - Bjak listed 952 postings of 96 roles;
      - Mindrift posted one AI-trainer role 77 times;
      - Speechify posted one role per US city (53 titles);
      - 690 jobs are on two or three boards.
    - **The rule** is in `int_job_postings`.
      - **Same company and title:** postings with the same company and title are one job, on any board and in any location. Company and title are compared lower-cased, letters and digits only, without a trailing legal form (Inc, GmbH…) or gender tags ((m/w/d)).
      - **Same description:** a company's postings with the same description, at least 300 characters long, are one job too. They take the alphabetically first of their titles, and two rounds of title → description → title join titles linked through a second description.
    - **Silver keeps every posting**, one row per source posting as before. From staging on, `posting_key` names a posting and `job_key` the job.
    - **Gold is one row per job.** `fct_job_postings` takes:
      - the earliest publish date;
      - listed and remote when any of its postings is;
      - the title, link and seniority of the newest listed posting;
      - the salary of the newest posting with a plausible one.

      Skills, locations, industries and types are the union over its postings. The new `bridge_job_sources` lists the boards a job is on, so the Source slicer finds it under each.
    - **The weekly trend** counts jobs per source. A job on two boards counts once for each, until decision 12.
    - **The history is rebuilt once to count jobs.** The two `hist_himalayas_*` tables are dropped and backfilled from silver. That loses the counts of 103 Himalayas jobs (0.4%) that had expired since 21 October. From then on, a job reposted after all its postings expired counts again.
    - **Rehearsed before building** (2026-11-03): the compiled models were chained over silver as one read-only query.
      - 44,179 postings make 38,280 jobs, one `fct_job_postings` row each;
      - 31,647 listed postings make 27,852 listed jobs;
      - every posting's skills reach its job;
      - the median plausible salary of listed jobs went from $131,778 (postings) to $134,824 (jobs).
    - **Not merged:** a role whose postings differ in both title and description (Pennylane's support role has two description variants, so it's two jobs), and a company written differently on different boards (Oura, ŌURA, Oura Health).
    - **Rolled out on 2026-11-03, in one go between two nightly runs:**
      1. `databricks bundle deploy`, for decision 10 and the HTML fix. The workspace copy of `transform/` was checked before step 2.
      2. Both `hist_himalayas_*` tables were dropped. They held 25,523 counted jobs in 13 day rows and 4,393 skill rows, counted through 2026-11-03 18:04 UTC.
      3. `transform_and_build` was triggered by hand, and it ran green: 98 tests pass, 27 models and the seed built, no warnings.
         - **Silver:** no description has HTML tags left, on any source. Posting skill tags fell from 237,790 to 231,414 (−2.7%, decision 10).
         - **Gold:** 44,179 postings make 38,278 jobs, 27,852 of them listed. 690 jobs are on more than one board, and the biggest job has 77 postings. 205,145 job × skill rows; DocuSign fell from 80 postings to 31 jobs.
         - **History:** 22,341 Himalayas jobs (from 25,420 postings), equal to silver, and 4,349 skill rows.
         - **Trend:** two complete weeks, 19 and 26 October, for every source.
      4. Next: refresh Power BI Desktop, where the Source slicer now goes through the new `Job sources` bridge.
12. **(2026-11-04) The weekly trend counts each job once, in the week it was first listed on any board.**
    - **Why:** the trend counted each board separately, so a job on two boards counted twice. Himalayas' copies couldn't be matched with the others once they expired. The Source slicer it allowed on the Rising skills page wasn't worth that.
    - **The rule** is `int_job_first_listings`. For each job, it gives the week Himalayas first listed it (by the day first seen) and the week Jobicy or Arbeitnow first did (by publish date), and the job counts in the earlier one. A board listing the job again, or another board listing it later, is the same job still listed, so it doesn't count again.
    - **How a week is counted:**
      - the jobs Jobicy or Arbeitnow first listed that week, recomputed from silver;
      - plus the jobs Himalayas first listed that week, from the frozen history, unchanged (decision 4);
      - minus the jobs on both whose later first listing fell that week.

      That last count can't be recomputed once the Himalayas posting expires. Two new incremental tables, `hist_himalayas_overlap_jobs_by_week` and `…_skills_by_week`, store it once per week, written by the build that completes the week. The trend shows exactly the weeks stored there.

      Example: Jobicy lists Acme on 20 October and Himalayas on 29 October. The week of 19 October counts 1 + 0 − 0 = 1, and the week of 26 October counts 0 + 1 − 1 = 0.
    - **Measured** (2026-11-04), against counting each board separately:
      - 13,512 and 17,129 jobs in the weeks of 19 and 26 October, instead of 13,677 and 17,611;
      - shares move by up to 0.3 pp: Go 6.1 → 5.8%, Machine Learning 11.7 → 11.4%;
      - the risers stay the same. Among the fallers, Linux goes from −0.6 to −0.8 pp and SQL leaves the top 5. Machine Learning turns from +0.1 to −0.1.
    - **Rehearsed** (2026-11-04, read-only): the new model files ran as first builds over that day's data.
      - **Week of 19 October:** 13,512 jobs, equal to an independent count from silver.
      - **Week of 26 October:** 17,129 jobs, which is the independent 17,084 plus the 45 expired Himalayas jobs the history kept.
      - **Shapes and limits:** 768 rows (2 weeks × 384 skills); no count went below 0; shares within 0.04 pp of the independent count.
    - **Rejected:**
      - **First listing per board:** a copy on another board in a later week counted again (17,403 jobs in the week of 26 October).
      - **Every week a board lists the job:** a repost is the same job still listed (18,194).
      - **Jobs listed during the week:**
        - Jobicy's and Arbeitnow's feeds are 7-day windows, while Himalayas jobs stay listed until they expire, about two months later.
        - Our Himalayas stock grows until its first big expiries in December (19,001 of 22,728 jobs). Himalayas went from 46% to 70% of the listed jobs between the two weeks, so nearly every tech skill seemed to rise 2–3 pp.
        - The Skills overview's Listed now shows current demand instead.
      - **Dating every job by the day first seen:** Arbeitnow's first run brought 4,161 jobs published the week before, so nearly every common skill seemed to rise 1–2.7 pp.
      - **Keeping the job keys of expired Himalayas jobs to match copies later:** a job key is the company and title hashed, so it would keep the expired job under another name (decision 4).
      - **Freezing Jobicy and Arbeitnow too:** a matcher fix would no longer reach their past weeks.
    - **Left imperfect:**
      - **Expired before matching:** a job counts twice when its Himalayas posting has already expired by the time the week of its later listing is stored.
      - **Late landings:** a Jobicy or Arbeitnow posting that lands more than two days late, after its week is stored, isn't matched.
      - **Floored skill counts:** frozen and live skill tags can differ by a job after an expiry or a matcher change, so a skill count is floored at 0. That didn't happen in the rehearsal.
    - **Power BI:** the trend has no source column, the Source slicer leaves the Rising skills page, and the Trend measures no longer combine sources.
13. **(2026-11-05) A job counts again, as a new opening, once none of its listings is live.**
    - **Why:** under decision 12, a repost never counted again on Jobicy and Arbeitnow, whose postings silver keeps forever. On Himalayas it did, once its earlier postings expired (a median of 59 days after first seen). Over the months, re-openings of the same company and title would have vanished on Jobicy and Arbeitnow while Himalayas kept counting them. Himalayas' weight in new jobs would have grown into a fake trend.
    - **The rule** is `int_job_openings`, which replaces `int_job_first_listings`. A listing starts a new opening when none of the job's earlier listings is still live:
      - a Jobicy or Arbeitnow listing counts as live for 8 weeks after it was published, because their feeds show only 7 days and we can't see when a job closes;
      - a Himalayas listing is live until it expires, which is when the Himalayas history already counts a job again.

      A role that's reposted continuously stays one opening.
    - **How a week is counted:** as in decision 12, but with openings instead of jobs.
      - The Jobicy and Arbeitnow openings come from silver.
      - The Himalayas openings come from the frozen history, which is unchanged.
      - The overlap tables now store what those two count twice: Jobicy/Arbeitnow openings + Himalayas openings − openings over all boards, frozen per week.
    - **A unit test** in `_int__models.yml` pins the rule with four made-up jobs:
      - a repost 9 weeks later;
      - reposts every few weeks;
      - Himalayas first, then Arbeitnow;
      - a Himalayas posting that expired early, followed by a new one.
    - **Measured before choosing:**
      - same-board reposts 7 or more days later: 325 jobs on Arbeitnow, 274 on Himalayas, 48 on Jobicy;
      - the longest gap so far is 26 days.
    - **Rehearsed** (2026-11-05, read-only): the result is identical to the trend built the day before, with 13,512 and 17,129 jobs and all 768 skill counts the same. The data, which starts on 7 October, has no 8-week gap yet, so no history table needed a rebuild.
    - **Rejected:**
      - **keeping one count per job;**
      - **a 4-week window:** it would recount roles that are only bumped;
      - **counting again 8 weeks after the last counted week, however often the job was reposted:** the Himalayas history can't do that without remembering expired jobs.
    - **Left behind:** dbt doesn't drop the old view `gold_staging.int_job_first_listings`.
14. **(2026-11-11) The weekly trend combines the three boards with fixed weights.**
    - **Why:** a skill's weekly share moved with the mix of boards, not only with demand.
      - **The boards differ:** a Himalayas job mentions about 7 skills, a Jobicy job about 4 and an Arbeitnow job about 3.
      - **Himalayas' volume swings with its feed:** its runs saw about 20,000 updated jobs on 1 and 2 November and about 4,000 on 3–5 November, against 11,000–13,000 before. Every run read back to its cutoff, so nothing was missed; the feed itself was that uneven.
      - **The result:** Himalayas went from 72% of the new jobs in the week of 26 October to 53% in the week of 2 November, and nearly every top skill fell 2–4 pp. CI/CD fell from 16.9% to 12.9%, but within each board it moved far less: Arbeitnow 7.6 → 6.9%, Jobicy 8.8 → 7.2%, Himalayas 20.2 → 18.1%. About half of the fall was the mix alone.
    - **The rule:** each board's own weekly share of a skill (its new jobs asking for the skill ÷ its new jobs) is combined with fixed weights: share = Σ weight × board's share. A board's weekly volume then only changes how precise its share is, never the line.
    - **The weights** are each board's share of all new jobs over the trend's complete weeks, recomputed on every build.
      - Every week in a build uses the same weights, so the weeks stay comparable. A new week shifts the whole line only slightly.
      - Weighting by volume keeps the line close to the Skills overview's shares, and gives the smallest board, Jobicy (about 1,400 jobs a week), the least say.
    - **A week where a board has no new jobs** (a week-long outage) uses the other boards, with their weights scaled up to 100%. The change from the week before uses only the boards with jobs in both weeks, so the missing board doesn't show up as a change.
    - **Counted per board, as openings (decision 13):** Jobicy and Arbeitnow from silver, through a scope per board in `int_job_openings`; Himalayas from the frozen history (decision 4).
      - **A job on two boards counts in each board's own share,** because it's part of both boards' samples. There's nothing to subtract, because the shares are never added up as counts.
      - **The difference is small:** jobs on more than one board are 1–3% of a week's jobs, and when decision 12 switched from counting per board to counting once, shares moved by at most 0.3 pp.
      - **Counting each job strictly once inside the weighted share** would need the board that listed it first, which can't be recovered for expired Himalayas jobs without new history tables.
    - **The job counts stay as they are:** `jobs` and `week_jobs` still count each opening once across the boards (decisions 12 and 13), for the tooltips, so a week's share is no longer exactly `jobs ÷ week_jobs`.
      - **The overlap history keeps being built, for these counts only;** the weighted share doesn't use it. It also still decides which weeks are complete.
      - **Why not retire it:** it costs nothing extra, a gap in a history table can never be filled, and "each job counts once" stays true for every number the report shows.
    - **The chance band moves into the model.** For each week, it's where the share would land by chance, at 95%, if no board's own share had changed since the week before: the previous week's share ± 1.96 × √(Σ weight² × q × (1 − q) × (1/n this week + 1/n the week before)), with n each board's new jobs per week and q its share over the two weeks together. Pooling the two weeks keeps the range from shrinking to nothing when a rare skill had no jobs the week before.
      - **Power BI draws it as a bar at each week** (error bars), and only when one skill is picked. A shaded ribbon looked wrong: each week's range is centred on the week before, so the ribbon trailed the line by a week, and its stretch between two weeks meant nothing. With bars, a point outside its own bar is a real change.
    - **The trend line's y-axis starts at 0 and reaches at least 5%** (`Trend axis max`). Scaled to the data alone, a rare skill filled the chart: Adaptive Planning's 0.05% → 0.1% (about 7 → 13 jobs a week) looked like a surge, with both points inside their chance bars. Above 5%, the axis follows the highest line or bar, so the top skills look as before. Rejected for now: hiding the trend of skills with too few jobs a week, which would also hide emerging skills while they're small.
    - **Rejected:**
      - **Averaging each board's week-over-week change, weighted by that week's volume:** also free of the bias and slightly more precise, but the line needs levels, and levels chained from changes drift.
      - **Equal weights:** Jobicy's small weekly samples would weigh as much as Himalayas'.
      - **Himalayas only:** it drops 40% of the jobs, and changes within Himalayas would still show.
      - **Weighting by board × industry as well:** the groups get small and noisy.
      - **Keeping the trend and adding a note:** the Rising skills ranking would keep showing the mix.
    - **Not fixed by weights:** a change in the kind of jobs one board posts. Himalayas' own CI/CD share fell from 23.2% to 20.2% to 18.1% over the three weeks, AWS from 24.1% to 21.8% to 20.2%. Checked in 5.11, step 1, there are two causes:
      - **The title fallback (Phase 4, decision 8), a one-off step, accepted.** From 31 October, about 12% of Himalayas' new jobs are kept for their title alone. They mention fewer skills and much less DevOps, so Himalayas' CI/CD share is about 1 pp lower with them. From the week of 2 November, every week includes them, so weeks compare like with like again. Leaving them out of the trend would need a flag in silver and split history counts, which can only be backfilled while those jobs are live (until mid-December).
      - **A batch of different jobs from Himalayas' feed,** first seen from 30 October to 3 November, about 5,000 of them on 1 November alone. They mention 5.2–6.4 skills instead of about 7.2, and CI/CD in 12–20% instead of 20–25%. They're real postings, so the trend keeps them. A single-week comparison will always show such a batch; 4-week windows (fix 3, once there's more history) would smooth it.
    - **Measured** (2026-11-11, read-only rehearsal after the nightly run; 5.11, step 3):
      - **Weights:** Himalayas 63.7% (27,881 jobs over the three weeks), Arbeitnow 26.6% (11,639), Jobicy 9.7% (4,245).
      - **CI/CD:** 17.5% → 15.7% → 14.0%, against 17.3% → 16.9% → 12.9% before. Its own share on each board in the week of 2 November equals the independent count from silver (Himalayas 18.1%, Arbeitnow 6.9%, Jobicy 7.2%).
      - **The week of 2 November, before → after:** SQL −2.3 → 0.0 pp, Azure −2.8 → −0.5, AWS −3.7 → −1.3, CI/CD −4.1 → −1.7, Kubernetes −2.3 → −1.0.
      - **Top 5 fallers:** CI/CD, AWS, Azure, Kubernetes, SQL before; CI/CD, Node.js, AWS, React, PostgreSQL after, each outside its chance band (the batch of 30 October – 3 November).
      - **Top 5 risers:** Excel, Microsoft Office, HubSpot, GDPR, Stripe before; Microsoft Office, Excel, Machine Learning, LLMs, Vulnerability Management after. LLMs (+0.5 pp) is inside its band.
      - **Unchanged:** `jobs` and `week_jobs` in all 1,152 rows (3 weeks × 384 skills). No share is empty, and no band is inverted.

## How it fits

```
nightly chain (18:00–18:30 UTC) ─► gold, incl. the new Himalayas history tables
                                     │  19:00 UTC: scheduled refresh (Import, Databricks connector)
                                     ▼
                     Power BI semantic model (My workspace) ─► report (4 pages)
                                                                  │  Publish to web (public embed code)
                                                                  ▼
                     https://robi4419.github.io/Nexus-Project/  (site/index.html, iframe + credits)
```

## Tasks

### 5.2 Himalayas history and the weekly trend
- New folder `models/history/` with two incremental models (`full_refresh: false`, contracts, schema `gold`):
  - `hist_himalayas_jobs_by_day`: `first_seen_date`, `jobs`, `counted_through` (the watermark);
  - `hist_himalayas_skills_by_day`: `first_seen_date`, `skill`, `jobs`, `counted_through`.
- `agg_skill_weekly_trend` gets a `source` column and Himalayas rows. Tests move to `week_start`, `skill` and `source`.
- Checks:
  - the backfill's totals match silver's Himalayas jobs per day first seen;
  - a second `dbt build` the same day appends nothing;
  - `dbt build --full-refresh` leaves the history alone;
  - Himalayas' first complete week is chosen from the data.
- **Done on 2026-11-01:**
  - **The backfill** counted 18,118 Himalayas jobs first seen from 21 to 31 October, and 128,530 job × skill rows. Both equal silver exactly, day by day.
  - **The weekly trend** starts with the week of 19 October for all three sources: Jobicy 1,467 jobs, Arbeitnow 4,555 and Himalayas 9,061. Himalayas' first run was on 21 October, but it caught up two days, so the week is kept; shares don't depend on a week's length.
  - **A second build** appended 0 rows. **`--full-refresh`** also appended 0 rows instead of replacing the tables: the Delta log shows a single `CREATE OR REPLACE`, the backfill.
  - **The new test `assert_himalayas_history_covers_silver`** fails the build if a day has more Himalayas jobs in silver than in the history, that is, jobs the history missed.
  - **Partial parsing:** the first `dbt build` reused a stale parse that missed the new YAML, so both models failed their contracts. `transform_and_build` now runs dbt with `--no-partial-parse`, which costs about 5 seconds a night.
- **First nightly append, 2026-11-01:**
  - the chain appended 1 day row (5,828 Himalayas jobs first seen that day) and 370 day × skill rows;
  - the history now counts 23,946 jobs, while silver has 23,937. The 9 missing from silver are early expiries from 21, 29 and 31 October, deleted overnight; the history kept their counts, as designed;
  - `assert_himalayas_history_covers_silver` passed.
- **Correction:** a week joins the trend once its Sunday is **two** days old (`week_start <= today - 8`), not one as first written. The week of 26 October appears with the 3 November build.

### 5.3 Your setup (any time)
1. Install Power BI Desktop from the Microsoft Store.
2. Create a Databricks access token named `power-bi`.
3. In Desktop, use File → Save as → Power BI project (`.pbip`) to create `dashboards/JobsAnalytics.pbip`. Turn on the TMDL format if Desktop asks.
4. Connect once with Get data → Azure Databricks to one gold table, so I can copy the exact query pattern Desktop writes.

### 5.4 Semantic model (TMDL)
- **Tables, imported:**
  - `dim_date`, `dim_skill`, `dim_location`, `dim_industry`, `dim_seniority`;
  - `fct_job_postings`, reduced to: `job_key`, `seniority`, `published_date`, `source`, `is_remote`, `is_listed_now`, `salary_mid_usd_yearly`, `salary_is_plausible`;
  - `fct_job_skills`: `job_key`, `skill`;
  - the three bridges;
  - `agg_skill_co_occurrence`, `agg_skill_weekly_trend`;
  - a 3-row source table shared by the facts and the trend.
- **Relationships:**
  - the dimensions filter `fct_job_postings`;
  - each bridge filters both ways between its dimension and the fact;
  - `fct_job_postings` filters `fct_job_skills`, and `dim_skill` filters `fct_job_skills`, the trend and co-occurrence;
  - the extra keys in `fct_job_skills` aren't imported, so there's only one path from each dimension.
- **Hierarchies:**
  - `dim_location`: region › country › city;
  - `dim_date`: year › quarter › month › day.
- **Measures:**
  - Jobs;
  - Jobs with skill;
  - Share of jobs;
  - Median salary (USD, plausible only; skill filters reach the jobs through `CROSSFILTER`);
  - Share with salary;
  - Week share and Share change;
  - Lift.
- **Check:** after a refresh, row counts and a few measures match SQL on gold.
- **Done on 2026-11-01:**
  - **Connection:** the Azure Databricks connector, authenticating with Account key (Desktop's name for an access token).
  - **The model:** written in TMDL. Desktop flagged two things on opening, both now fixed:
    - descriptions (`///`) aren't allowed on relationships;
    - "Measures" is a reserved table name, so the table is `_Measures`.
  - **The check** is `DAXQueries/Query 1.dax`. All 10 values match SQL on gold exactly:
    - Jobs 34,764; Jobs with skill 27,643; Python share 21.8%;
    - Jobs with salary 9,162; Median salary $132,500; Python median salary $135,000;
    - Europe jobs 16,598 (through the location bridge); Listed now 24,464;
    - Python week share 24.1% (all three sources, week of 19 October); Skill pairs 37,342 rows.

### 5.5 Report pages
You build the pages from decision 7 with my step-by-step guidance. Every page gets a footer that says:
- Jobs: Jobicy · Arbeitnow · Data sourced from Himalayas (linked to himalayas.app);
- Exchange rates: ECB via Frankfurter;
- Places: GeoNames (CC BY 4.0).

Pages use Fit to page, at a 16:9 ratio.

- **Skills overview, done on 2026-11-01:** cards for Jobs and Jobs with skill, the top 30 skills and the categories by share of jobs (clicking a category filters the skills), and seven slicers: listed now, date, place, seniority, job type, industry and source.
- **Salaries, done on 2026-11-02:**
  - cards for the median, the 25th and 75th percentiles, jobs with salary and share with salary;
  - **best-paid skills:** the 20 highest medians, with whiskers from the 25th to the 75th percentile (error bars);
  - **pay vs demand:** a scatter of the 30 skills with the most salaried jobs;
  - **salary ladder:** the median by seniority as a line with a 25th–75th percentile band, and jobs with salary on a second axis;
  - **jobs open to candidates in each region:** the median by region, drilling down to countries, without Antarctica.

  A new measure, `Median salary (enough jobs)`, is blank below 30 salaried jobs, so a handful of salaries can't top a chart. The slicers are synced with the Skills overview's. Arbeitnow lists no salaries (0 of 4,827 listed jobs), and the page says so.
- **No salary map:** 195 of the 202 countries with at least 30 salaried jobs get most of them from the same 348 jobs, each listing more than 40 countries. A map would paint most of the world with those jobs' median ($87,000). A job's countries are where candidates may live, hence the region chart's title.
- **Checked against SQL on gold** (listed now): the 20 best-paid skills, the ladder (Intern $46,800 to Executive $219,885) and the region medians (North America $140,000, Europe $84,000, LATAM $75,000) match.
- **Skills asked together, done on 2026-11-03:**
  - **a skill dropdown, synced on all three pages,** with nothing picked by default. On Skills overview and Salaries the rankings ignore it, and the cards, the ladder and the region chart follow it;
  - **most often asked with the picked skill:** its 15 most frequent partners, by share of its jobs;
  - **heatmap:** the lift between the 15 most common skills, or between the picked skill and its 14 most frequent partners;
  - **a hidden tooltip page** puts each cell into words: the jobs asking for both, the shares in both directions and the lift.

  The dropdown filters `Skill pairs` to one skill, so the heatmap takes its axes from two tables related to nothing, `Heatmap rows` and `Heatmap columns`. A Top N filter by `Heatmap rank` picks the rows, and `Heatmap lift` is blank in the columns outside them. The pairs are counted over all jobs, so the page has no job slicers. The Filters pane is hidden from viewers, so the visual-level filters stay as designed.
- **No drill-through into Skills asked together itself:** Power BI applies a drill-through as a page filter, which leaves a dropdown on the same field offering only the drilled skill, and a drill-through can't set or clear a slicer. The synced dropdown carries a picked skill between pages instead.
- **Drill-through into a copy, added on 2026-11-07:**
  - **The target:** a hidden page, **Asked with**, is a copy of Skills asked together without the dropdown. Its drill-through field is `Skill[Skill]`, with **Keep all filters** off, so a dropdown pick on the source page doesn't come along.
  - **How to use it:** right-click any skill bar → Drill through → Asked with. For touch screens, a **"See what it's asked with →"** button on Skills overview, Salaries and Rising Skills drills with the selected bar. It's disabled until exactly one bar is selected.
  - **Tested:** both work in Desktop and on the public report.
  - **The cost:** the two pages' design has to be kept in step by hand.
  - **The buttons** sit in a corner where no visual overlaps them. A visual clicked in reading mode rises above anything overlapping it unless *Maintain layer order* is on.
- **Rising skills, done on 2026-11-04:**
  - **Rising and Falling:** the 10 skills whose share of each week's new jobs rose or fell most, latest complete week against the week before, in percentage points. The tooltips hold both weeks' shares and jobs.
  - **Weekly share line:** the latest week's top 10 skills, or the picked ones. Its title follows what it shows.
  - **A note** on how a week counts jobs (decisions 12 and 13), and on Himalayas' title fallback from 31 October. **Removed on 2026-11-07,** when the page was re-laid out: the movers moved to a left column, and a Week slicer above the line chart narrows its weeks. The slicer saves no range, so each new week shows by default.

  **Decided on 2026-11-05: the trend keeps combined shares for now,** not mix-adjusted ones. The investigation that raised the question:
  - **What happened** (investigated 2026-11-05): from 3 November, Himalayas posts and updates about 2,000 jobs a day instead of about 6,000. Fresh tech postings fell from 1,700–2,400 a day to 650–800, after a mass re-bump of two-week-old jobs on 1–2 November.
  - **Not an API change:** the fields, `pubDate`, the sort order, the page size and the release notes are unchanged. The feed's `totalCount` fell from about 128,000 to 112,841.
  - **The effect:** Himalayas went from 73% of the week's new jobs to 42% so far. The combined shares then show fake falls for tech skills (CI/CD −5.9 pp, AWS −5.6 pp) and fake rises for skills common on Arbeitnow.
  - **Not done for now:** mix-adjusted shares, where each skill's share is computed within each board group and combined with fixed weights, so one board's volume can't move it. Until then, a swing in one board's volume shows up as movers.

  The dropdown filters only the line, and clicking a bar shows that skill's line. The two bar charts don't filter each other. The trend counts all three boards together, so the page has no Source slicer. Checked against gold after the 2026-11-04 build: the 20 movers and the 10 lines match.

### 5.6 Account and publishing (you, once the report is ready; the trials start counting at sign-up)
1. Start a Microsoft 365 trial, which creates the `…onmicrosoft.com` account. Cancel the subscription before it bills; the account stays.
2. At app.powerbi.com, start the 60-day Pro trial.
3. In the admin portal, set Tenant settings → Export and sharing → Publish to web to **Enabled**.
4. In Desktop, publish to My workspace.
5. In the service, enter the token in the model's settings and schedule a daily refresh at 19:00 UTC.
6. Use File → Embed report → Publish to web, with a placeholder image. Copy the iframe code.
- **Done on 2026-11-05:**
  - **The account:** a Microsoft 365 Business Basic trial created the tenant `vasairobert.onmicrosoft.com`. Basic was chosen because it includes no Power BI Pro, so the separate Power BI trial stays available. You're its admin. Turn recurring billing off in the admin center, so the trial expires instead of billing.
  - **Power BI:** first a free licence, then the trial.
  - **Publish to web:** already enabled for the whole tenant. "Block public internet access" is off, which Publish to web requires.
  - **Published** from Desktop to My workspace.
  - **Credentials:** the first try failed with *403 Unauthorized/Forbidden*. The old `power-bi` token had also been exposed in a screenshot, so it was revoked. The new `power-bi` token was accepted, so Free Edition does accept the Power BI service and no gateway is needed. Desktop needs the new token too (Data source settings).
  - **Refresh:** daily at 19:00 UTC, with failure e-mails to the owner. A manual refresh succeeded.
  - **Embed:** the iframe is in `site/index.html`, sized by CSS (16:9 plus the 36px page bar).
- **Dates to watch:**
  - **4 Jan 2027:** the `power-bi` token expires. Renew it in the service (Data source credentials) and in Desktop before then.
  - **4 Dec 2026:** the Power BI trial ends, and the public embed most likely stops with it. Decide before then between Pro (about $14 a month) and a screenshot (decision 1).
  - **25 Nov 2026:** the `Personal Project` token expires. If it's the one in `.env`, renew it, or the nightly pipeline stops.

### 5.7 Public repository
- Replace the real jobs in `tests/fixtures/jobicy_page.json` (1) and `arbeitnow_page.json` (2) with made-up ones; `pytest` must stay green.
- Scan `git log -p --all` for Databricks tokens (`dapi…`), `.env` contents, passwords and keys.
- **Your call:** the commits carry `vasairobert@yahoo.com`. Either accept it, or use the GitHub noreply address for future commits.
- Optional: add a `LICENSE` file.
- **You:** Settings → Change visibility → Public.
- **Done on 2026-11-05, except the visibility change:**
  - **Fixtures:** the 3 real jobs (1 Jobicy, 2 Arbeitnow) were replaced with made-up ones in the same format; all 459 tests pass. The old commits keep those 3 public postings, which you accepted. The Himalayas fixture was made-up from its first commit, so no Himalayas data is anywhere in the history.
  - **History scan** of all 124 commits, on every branch, printing only the file names that matched:
    - no Databricks token, no private key, no Bearer token, no secret variable with a value, and no `.env` or credentials file ever committed;
    - the flagged `TOKEN` lines in `transform/skills.py` and its tests are the word-splitting regex and test cases.
  - **Public, by your choice:**
    - **the e-mail** `vasairobert@yahoo.com` on 116 commits, which stays;
    - **the Databricks host and SQL warehouse HTTP path** in `expressions.tmdl` (decision 8). They identify the workspace but grant nothing without a token.
  - **No `LICENSE` file:** the code is readable, with all rights reserved.

### 5.8 GitHub Pages
- `site/index.html` with:
  - the title and a short description;
  - the iframe, with a fallback image;
  - the credits with links, and a link to the repository;
  - no JobPosting structured data (Himalayas' terms).
- `.github/workflows/pages.yml` deploys `site/` on a push to `main` that changes it.
- **You:** Settings → Pages → Source: GitHub Actions.
- **Written on 2026-11-05:**
  - **Changed on 2026-11-07: the report fills the whole window,** with no margins, title, intro or footer. The source credits, including "Data sourced from Himalayas" with its link, stay visible in the report's own footer on every page, which is what Himalayas' terms require.
  - **`site/index.html`, first version:** report and credits only, as you chose, in the report's colours. Until 5.6, a placeholder stands where the iframe goes. A comment there shows where to paste the embed code, and the screenshot line to use if the embed ever stops.
  - **`pages.yml`:** uses the current major versions of the actions (checkout v7, configure-pages v6, upload-pages-artifact v5, deploy-pages v5). It can also be started by hand from the Actions tab.
  - **First deploy:** happens after the merge to `main`, because the `github-pages` environment only accepts deploys from the default branch.

### 5.9 Verify
1. `pytest`, `dbt build` and the history checks (5.2) pass.
2. In Desktop, the counts match gold.
3. The first scheduled refresh in the service succeeds.
4. The page works in a private browser window:
   - it loads with no sign-in;
   - data can't be exported;
   - the credits show.
5. The numbers change after the next nightly refresh.
- **Checked on 2026-11-05:**
  - **Tests and build:** `pytest` passes (459 tests). The nightly `dbt build` ran green with the new trend models and their unit test (18:04–18:13 UTC).
  - **The public link,** in a private window with no sign-in:
    - it opens on Skills overview, and the hidden tooltip page has no tab;
    - the cards match gold: 29,449 listed jobs, 24,577 with skills, and Python 24.2%, AWS 19.4%, CI/CD 18.1%, SQL 17.9%, Azure 15.7%;
    - Salaries shows 9,314 jobs with a salary and a $135,000 median;
    - the heatmap tooltips work, data can't be exported, and the credits show on every page.
  - **Confirmed on 2026-11-07:** the first scheduled refresh (2026-11-06, 19:00 UTC) succeeded, and the report's numbers moved.
  - **Found while checking:** a Desktop session had dropped the Listed now default on Skills overview and Salaries. It had also saved fixed ranges in their date slicers (1 Oct – 5 Nov) and in the new Week slicer (19 – 26 Oct). All three were restored or cleared before the next publish (see the date-slicer pitfall). Before committing report changes, check for saved slicer filters.

### 5.11 Board weights in the weekly trend (decision 14)
On the branch `trend-board-weights`. The nightly run builds dbt from this folder (`./dbt` is mounted into Airflow), so:
- dbt files change only between runs: after the chain is green (about 18:30 UTC) and before 18:00 the next day;
- from the build in step 4 until the merge, the branch stays checked out, so the nightly run keeps building the new models;
- the report is published to the service only after the merge, so the published model never expects columns that gold lacks.

Already on the branch: the trend line chart's changes of 2026-11-11, made in Desktop: the y-axis from 0, straight lines, and a chance band (`Chance range low` and `Chance range high`) shown only when one skill is picked. Step 5 moves the band's formula into dbt.

1. **Check the title fallback (read-only, counts only).** From bronze's raw Himalayas records, compare the jobs kept by category with those kept by title since 31 October: skills per job, and the shares of the top 10 skills. If they differ a lot, that's a separate decision, not part of this branch.
   - **Done on 2026-11-11** (Himalayas postings by first-seen week; a posting is kept by title when no copy in bronze has a parent category):

     | Week | Kept by | Postings | Skills per posting | CI/CD | AWS | Python | Kubernetes |
     |---|---|---|---|---|---|---|---|
     | 19 Oct | category | 9,054 | 7.23 | 22.9% | 23.7% | 29.3% | 13.5% |
     | 26 Oct | category | 13,360 | 6.61 | 20.5% | 21.8% | 26.2% | 13.0% |
     | 26 Oct | title | 1,210 | 5.13 | 10.1% | 13.7% | 20.2% | 7.0% |
     | 2 Nov | category | 7,060 | 6.40 | 18.7% | 20.5% | 26.5% | 12.0% |
     | 2 Nov | title | 1,005 | 4.71 | 8.6% | 12.5% | 20.1% | 6.3% |

   - By first-seen day, the category-kept postings mention about 7.2 skills from 21 to 28 October, 5.2–6.4 from 30 October to 3 November (4,986 postings on 1 November), and mostly 6.6–7.1 from 4 to 10 November. CI/CD is back at about 25% on 9 and 10 November.
   - **Decided:** the title fallback stays in the trend as a one-off step, and the batch stays as real data (decision 14, "Not fixed by weights").
2. **dbt:**
   - `int_job_openings`: two more scopes, `jobicy` and `arbeitnow`, each looking only at its own board's listings, with the same rule. The existing scopes stay, so the overlap history doesn't change. Update the scope's accepted values and the unit test's expected rows.
   - New view `int_skill_weekly_by_board`: one row per complete week × board × skill, with `skill_jobs` and `board_jobs`.
     - Jobicy and Arbeitnow come from their scopes and `int_job_skills`.
     - Himalayas comes from `hist_himalayas_jobs_by_day` and `hist_himalayas_skills_by_day`.
     - The weeks are those `hist_himalayas_overlap_jobs_by_week` has stored, as now.
   - New mart `agg_trend_board_weights`: one row per board, with `board`, `jobs` over the trend's weeks, and `weight`. It has a contract and tests: the primary key, each weight between 0 and 1, and the weights summing to 1.
   - New view `int_skill_weekly_weighted`: one row per week × skill, with `share`, `prev_share`, `share_change`, `chance_low` and `chance_high`, including the missing-board rule. A unit test pins it with made-up rows: three boards over two weeks, then a week with one board missing.
   - `agg_skill_weekly_trend` keeps `jobs` and `week_jobs` (each opening once) and takes its shares, change and chance band from `int_skill_weekly_weighted`. `prev_jobs` goes. The contract checks that the share is between 0 and 1, and that `chance_low` ≤ `chance_high`.
   - Descriptions in the YAML and `_docs.md`, and the model list in the dbt README.
3. **Rehearse, read-only,** with `dbt show` over the day's data, as for decisions 12 and 13:
   - The weights sum to 1. A rough count from silver on 2026-11-11 expects about 63% Himalayas, 27% Arbeitnow and 10% Jobicy.
   - Each board's share matches an independent count from silver. For example, CI/CD in the week of 2 November: Himalayas 18.1%, Arbeitnow 6.9%, Jobicy 7.2%.
   - CI/CD's weighted line is about 17.5% → 15.7% → 14.0%, against 17.2% → 16.9% → 12.9% now.
   - `jobs` and `week_jobs` are unchanged from the current mart.
   - The top 5 risers and fallers before and after go into decision 14's Measured line.
4. **Build:** with the branch checked out, trigger `transform_and_build` by hand after the nightly run, as in decision 11's rollout. All tests pass, and the new columns are in gold.
   - **Done on 2026-11-11:** triggered at 18:22 UTC, green at 18:31. `dbt build`: PASS=153, WARN=0, ERROR=0, including both unit tests and `assert_trend_board_weights_sum_to_one`.
5. **Power BI (close Desktop first, because I edit the TMDL):**
   - `Weekly skill trend` imports `share`, `prev_share`, `share_change`, `chance_low` and `chance_high`, hidden.
   - The new table `Trend board weights` (`board`, `weight`) feeds a measure that names the weights, such as "Boards weighted: Himalayas 63% · Arbeitnow 27% · Jobicy 10%".
   - Measures:
     - `Week share`, `Previous week share` and `Share change` read the new columns, so the ranking measures that build on them follow;
     - `Chance range low` and `Chance range high` read the band, still only when one skill is shown;
     - the count measures stay.
   - The trend line's subtitle and the movers' subtitle name the weights.
   - **You:** refresh in Desktop, compare with the rehearsal, clear test selections, and save. I check the saved files for slicer filters.
   - **Done on 2026-11-11:**
     - **The model:** the five trend columns and `Trend board weights` imported. The measures read them, and `Board weights` and `Trend subtitle` are new.
     - **The trend line:** the y-axis starts at 0, the lines are straight, and the legend replaces the series labels. The chance range shows as a bar at each week, not a shaded ribbon (decision 14), and the subtitle, a measure, names the weights and explains the bars.
     - **Checked in Desktop:** the subtitle reads "Himalayas 64% · Arbeitnow 27% · Jobicy 10%"; nothing picked shows 10 lines without bars; Microsoft Office falls below its range on 26 October and rises above it on 2 November.
     - **Saved by Desktop and undone:** a fixed start date (19 October) in the Week slicer, the opening page switched to Rising Skills, and layout noise (the Filters pane width, sub-pixel moves of the movers charts, an empty filter on the skill dropdown).
6. **Docs, commit, PR and merge.** Then publish to the service, and confirm that the next scheduled refresh succeeds.
   - Docs: decision 14's Measured line, `PLAN.md`, the repo layout, and a pitfall about board mix.

## Concepts you'll meet
- **Semantic model:** Power BI's layer of tables, relationships and measures that every visual queries. **Import** keeps a compressed copy, refreshed on a schedule.
- **PBIP, TMDL and PBIR:** a Power BI project saved as folders of text. TMDL describes the model, PBIR the report pages, so git can show what changed.
- **Filter direction:** a relationship passes filters from the one side to the many side. "Both directions" also passes them back; bridges need it.
- **DAX measure:** a formula evaluated for each visual's filters, for example share of jobs = jobs with the skill ÷ all jobs in the same filters.
- **Incremental dbt model:** a table that a build appends to instead of rebuilding, using `is_incremental()` and a watermark. `full_refresh: false` protects it from `--full-refresh`.
- **Publish to web:** a public, anonymous embed of a report through an iframe.

## Pitfalls
- **Publish to web exposes the whole model,** not just what the pages show. Never import a column you wouldn't publish.
- **The history tables can't be rebuilt** once Himalayas jobs expire. Never drop them, and keep `full_refresh: false`.
- **Bridges count a job once per place, industry or type.** Jobs measures count rows of `fct_job_postings`, never rows of a bridge.
- **The two `agg_` tables ignore the dashboard filters.** Their pages say so.
- **The trials start counting at sign-up,** and the embed most likely stops when Pro lapses.
- **Heavy use of a public report is throttled** for a while; the placeholder image covers it.
- **An expired Databricks token breaks the refresh.** Power BI emails you; renew the token in the model's settings.
- **Measures must live in the model.** Publish to web doesn't support measures defined only in a report.
- **TMDL written by hand:**
  - descriptions (`///`) work on tables, columns, measures and parameters, but not on relationships;
  - "Measures" is a reserved table name;
  - Desktop adds a `lineageTag` to every object on its next save.

  Close Desktop before editing the files.
- **Two routes from one dimension to a table are ambiguous** in Power BI. So `Job skills` takes only `job_key` and `skill`, and every job filter reaches it through `Job postings`. Its copies of the job columns in gold are for SQL.
- **A measure filter on a chart whose axis is a hierarchy also works at the lower levels.** On the region chart (Region › Country), "Median salary (enough jobs) is not blank" left out the countries under 30 before each region's median was computed, which moved APAC from $77K to $81K. The measure is already blank below 30, so that chart has no such filter.
- **A date slicer saves a fixed end date** once it has a selection, and the days added by later refreshes then fall outside the default. The Date slicers are cleared, so they save no filter.
- **A visual takes one Top N filter.** The heatmap's columns follow its rows through `ALLSELECTED` in `Heatmap lift` instead.
- **A matrix has no Tooltips well.** A report-page tooltip shows the extra values.
- **A slicer's Single select keeps one item always selected.** The skill dropdown uses Ctrl to multi-select instead: a click picks one skill, and clicking it again clears it.
- **Test the picked skill on the dropdown's own column, `Skill[Skill]`.** On `'Skill pairs'[skill]`, each bar's own filter can leave a single skill, so `HASONEVALUE` was true with nothing picked.
- **A chart's Top N filter also filters its title measure.** On the trend line, `ISFILTERED ( Skill[Skill] )` was true with nothing picked, so the title said "the picked skills". `Trend line title` compares the skills shown with the latest week's top 10 instead.
- **Selections in different visuals intersect.** A bar clicked in Rising and one Ctrl+clicked in Falling leave no skill, so the trend line is empty; Ctrl+click adds skills only within one visual or slicer. The two charts were kept, and the trend line's title says what happened and points to the dropdown. `COUNTROWS` of an empty table is blank, which counts as 0 in a comparison, so the title tests `ISEMPTY` first.
- **A `%` format makes a difference of shares read as growth:** 0.02 shows as "+2.0%". Share changes are multiplied by 100 and formatted `+0.0" pp"`.
- **A share pooled over several boards moves with the boards' mix.** A Himalayas job mentions about 7 skills and an Arbeitnow job about 3, so a week with fewer Himalayas jobs lowers nearly every skill. The weekly trend weights each board's own share (decision 14); any new chart that pools the boards across weeks has the same trap.
- **Spark's `greatest()` and `least()` skip NULLs:** `greatest(NULL, 0)` is 0, not NULL. The first week's chance band came out as 0 until a `case` kept it NULL.

## Repo layout additions

```
dbt/job_listings/models/history/
    hist_himalayas_jobs_by_day.sql        ← frozen counts per day first seen
    hist_himalayas_skills_by_day.sql      ← … per day first seen × skill
    hist_himalayas_overlap_jobs_by_week.sql    ← jobs also on Jobicy or Arbeitnow, per week (decision 12)
    hist_himalayas_overlap_skills_by_week.sql  ← … per week × skill
    _history__models.yml
dbt/job_listings/models/intermediate/int_job_openings.sql  ← the weeks each job's openings began (decision 13), per board too (decision 14)
dbt/job_listings/models/intermediate/int_skill_weekly_by_board.sql  ← each board's weekly counts (decision 14)
dbt/job_listings/models/intermediate/int_skill_weekly_weighted.sql  ← the board-weighted share, change and chance band
dbt/job_listings/models/marts/agg_trend_board_weights.sql           ← the board weights
dbt/job_listings/tests/assert_trend_board_weights_sum_to_one.sql
dashboards/
    JobsAnalytics.pbip
    JobsAnalytics.SemanticModel/definition/   ← TMDL: tables, relationships, measures
    JobsAnalytics.SemanticModel/DAXQueries/   ← the check against gold
    JobsAnalytics.Report/                     ← the pages
site/
    index.html                            ← public page with the iframe and credits
.github/workflows/pages.yml               ← deploys site/ to GitHub Pages
```
