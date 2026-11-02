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
- [ ] 5.5 Report pages (you build them, I guide): skills overview, rising skills, salaries, skills asked together
- [ ] 5.6 Account and publishing: tenant, Pro trial, Publish to web, daily refresh
- [ ] 5.7 Make the repository public: made-up fixtures, history scan, author email, licence
- [ ] 5.8 GitHub Pages site with the iframe
- [ ] 5.9 Verify end to end
- [ ] 5.10 Docs, commit, PR and merge

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
6. **I write the semantic model, and you build the visuals.** The model is TMDL text in the PBIP project: tables, Databricks queries, relationships, hierarchies and measures, reviewable in git. You build the pages in Desktop with my step-by-step guidance. Everything is committed, except Desktop's local cache and settings.
7. **Four pages, each with a credits footer, starting on jobs listed now:**
   - **Skills overview:** top skills and categories by share of jobs, with filters for region and country, industry, seniority, job type and date.
   - **Rising skills:** biggest risers and fallers week over week, and a trend line per skill.
   - **Salaries:** median yearly salary in USD by skill, seniority and region, using plausible salaries only; also the share of jobs listing a salary.
   - **Skills asked together:** a co-occurrence heatmap, and "often asked with X" ranked by lift.

   The overview and salary pages start filtered on `is_listed_now`, and a slicer includes the rest. The two `agg_` tables ignore the dashboard filters by design (Phase 3).
8. **The Databricks host and HTTP path are two Power Query parameters, committed with the model.** They aren't credentials: the token is never in the project files, because Desktop and the service store credentials separately. A new token named `power-bi` can be revoked without touching dbt's.
9. **The published model refreshes daily at 19:00 UTC,** after the nightly chain (green by about 18:30), with refresh-failure emails on.

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

### 5.6 Account and publishing (you, once the report is ready; the trials start counting at sign-up)
1. Start a Microsoft 365 trial, which creates the `…onmicrosoft.com` account. Cancel the subscription before it bills; the account stays.
2. At app.powerbi.com, start the 60-day Pro trial.
3. In the admin portal, set Tenant settings → Export and sharing → Publish to web to **Enabled**.
4. In Desktop, publish to My workspace.
5. In the service, enter the token in the model's settings and schedule a daily refresh at 19:00 UTC.
6. Use File → Embed report → Publish to web, with a placeholder image. Copy the iframe code.

### 5.7 Public repository
- Replace the real jobs in `tests/fixtures/jobicy_page.json` (1) and `arbeitnow_page.json` (2) with made-up ones; `pytest` must stay green.
- Scan `git log -p --all` for Databricks tokens (`dapi…`), `.env` contents, passwords and keys.
- **Your call:** the commits carry `vasairobert@yahoo.com`. Either accept it, or use the GitHub noreply address for future commits.
- Optional: add a `LICENSE` file.
- **You:** Settings → Change visibility → Public.

### 5.8 GitHub Pages
- `site/index.html` with:
  - the title and a short description;
  - the iframe, with a fallback image;
  - the credits with links, and a link to the repository;
  - no JobPosting structured data (Himalayas' terms).
- `.github/workflows/pages.yml` deploys `site/` on a push to `main` that changes it.
- **You:** Settings → Pages → Source: GitHub Actions.

### 5.9 Verify
1. `pytest`, `dbt build` and the history checks (5.2) pass.
2. In Desktop, the counts match gold.
3. The first scheduled refresh in the service succeeds.
4. The page works in a private browser window:
   - it loads with no sign-in;
   - data can't be exported;
   - the credits show.
5. The numbers change after the next nightly refresh.

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

## Repo layout additions

```
dbt/job_listings/models/history/
    hist_himalayas_jobs_by_day.sql        ← frozen counts per day first seen
    hist_himalayas_skills_by_day.sql      ← … per day first seen × skill
    _history__models.yml
dashboards/
    JobsAnalytics.pbip
    JobsAnalytics.SemanticModel/definition/   ← TMDL: tables, relationships, measures
    JobsAnalytics.SemanticModel/DAXQueries/   ← the check against gold
    JobsAnalytics.Report/                     ← the pages
site/
    index.html                            ← public page with the iframe and credits
.github/workflows/pages.yml               ← deploys site/ to GitHub Pages
```
