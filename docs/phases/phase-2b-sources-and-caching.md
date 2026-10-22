# Phase 2b: More sources and incremental silver

**Goal:** two more job sources, **Arbeitnow** and **Himalayas**, flowing through the same pipeline as Jobicy (landing → bronze → silver → checks). Silver should also do work in proportion to **new or changed** jobs, not the whole history. Today `silver_skills` re-matches every job ever seen (94 s for 1,447 jobs), and `silver_jobs` re-cleans every description. Himalayas would add about 600 jobs a day.

**Done when:**
- `pytest` passes, including new tests for the caches, the location parser, the DE/FR seniority rules, the mapping files and both API clients.
- The `ingest_arbeitnow` and `ingest_himalayas` DAGs run daily and land files.
- `transform_jobs` builds silver from all three sources with every error check green. The checks are extended per source.
- A second Job run with no new data matches **0** jobs. The matching time is measured before and after the prefilter and the cache.
- No expired Himalayas job remains in silver, and expired Himalayas files are purged from landing and bronze.
- A short hand-check of the new sources is recorded (skills, seniority, locations).

## Progress
- [x] 2b.1 Branch, plan doc, `PLAN.md`
- [x] 2b.2 Faster skill matching: an anchor-word prefilter and a persistent skill cache (built and measured on Jobicy first)
- [x] 2b.3 Reference data: complete country list, GeoNames cities, `industries.csv`, `job_types.csv`, `levels.csv`
- [x] 2b.4 `transform/`: location parser, DE/FR seniority rules, fallback levels via `levels.csv`
- [x] 2b.5 Arbeitnow ingestion: client, landing, tests, `ingest_arbeitnow` DAG
- [x] 2b.6 Himalayas ingestion: client (API key, incremental, category filter), landing, tests, `ingest_himalayas` DAG
- [x] 2b.7 Bronze tasks for both sources
- [x] 2b.8 Silver: conform both sources; `is_remote`; mappings; per-source checks
- [x] 2b.9 Himalayas retention: purge expired jobs from bronze (landing is purged by the DAG since 2b.6)
- [ ] 2b.10 Verify end to end, and hand-check the new sources
- [ ] 2b.11 Commit, PR and merge

---

## What the sources look like (profiled 2026-10-20)

| | **Arbeitnow** | **Himalayas** |
|---|---|---|
| Access | public, no key; "please do not abuse", a link back appreciated | free API key: 60 requests/minute, 10,000/day; without a key, an unknown shared limit |
| Paging | `?page=N`, 300 jobs per page; the feed ends at about **page 28** | `cursor` / `nextCursor`, **at most 20 jobs per request** |
| Size | a rolling **7-day window** of about 5,000 jobs (about 40 MB) | **128,426** jobs in total; about **1,800 new a day**; refreshed daily |
| Remote | **8% remote**; mostly on-site jobs in European cities | essentially all remote |
| Location | free text: a city ("Berlin"), "City, Region, Country" ("Utrecht, Utrecht, Nederland"), a country, "Remote", or empty (2.6%) | `locationRestrictions`: country **names**, US 54%, Philippines 10%; empty means worldwide (2.6%) |
| Language | **43% of descriptions in German**; French job types too | 93% English |
| Seniority | none; 61% of titles match no current rule. German titles use "(m/w/d)", "Werkstudent", "Praktikum", "Leiter" | `seniority` list: Mid-level, Senior, Manager, Entry-level, Director, Executive |
| Job types | mixed DE/EN/FR, some of them levels: "Unbefristeter Arbeitsvertrag" (permanent contract), "berufserfahren" (experienced), "Werkstudent" | Full Time, Contractor, Part Time, Intern, Temporary, Other |
| Categories | role-like `tags` (Engineering, IT, Finance, Team Leader…) | 20 `parentCategories` |
| Salary | none | 25% of jobs; 12 currencies (CLP isn't published by the ECB); annual, hourly or monthly |
| Dates | `created_at`, Unix seconds | `pubDate` and `expiryDate`: seconds in practice, though the docs say milliseconds. Listing lifetime: median and max **60 days** |
| Skill coverage, current list | 69% | 64% |
| Terms | "free public API, please do not abuse" | attribution with a visible link; apply only through `applicationLink`; **no redistribution to job boards or aggregators**; **remove jobs once they expire** |

## Decisions (2026-10-20)

1. **Merge Phase 2 first** (PR #3), then do this on its own branch, `phase-2b-sources-and-caching`.
2. **Cache first, then the sources.** The cache is measured on today's Jobicy data, so silver is ready before Himalayas' volume arrives.
3. **Content-addressed caches.** A cache row is keyed by a hash of the step's **inputs** and a **version** of the code and reference data that produce it. A job is reprocessed only when its inputs or the version change. Changing `skills.csv` or `skills.py` re-matches everything once, automatically.
4. **Himalayas complies strictly with its terms:**
   - silver keeps a Himalayas job only until its `expiryDate`;
   - landing files and bronze rows whose jobs have all expired are purged;
   - `url` is the API's `applicationLink`;
   - dashboards (Phase 5) credit Himalayas with a visible link.
5. **Himalayas, Tech categories only:** Developer, Data Science, Product, Design, Hardware Engineer, Research & Development. That's about 33% of jobs, roughly 600 a day. The API can't filter by category, so the filter is applied before landing. It saves storage and processing, not requests.
6. **Himalayas is fetched incrementally:** newest first, until reaching jobs older than the previous run's newest one (with a 1-day overlap). The first run covers the last 7 days (changed to 2 days by decision 21). It needs a free API key, `HIMALAYAS_API_KEY` in the root `.env` (you add it; the compose file already loads `.env` into Airflow).
7. **Arbeitnow is downloaded in full every day** (about 28 polite requests), as with Jobicy, so `times_seen` and `is_listed_now` keep the same meaning. **All jobs are kept**, including on-site ones, with a new `is_remote` column in `silver.jobs`.
8. **Arbeitnow's cities map to countries through GeoNames**: the cities list with population over 15,000 (geonames.org, CC BY 4.0, credited in the docs). "City, Region, Country" strings are parsed, and an ambiguous city name takes the most populous match. Locations left unmatched stay `unknown`. That's an **error** for Jobicy and Himalayas, and a **warning** with the unknown share for Arbeitnow.
9. **German and French rules for seniority and job types:**
   - keywords such as Werkstudent, Praktikum, Stagiaire and Alternance → Intern; Teamleiter → Lead; Leiter/Leitung, Directeur and Geschäftsführer → Director/Executive, with trap tests;
   - gender suffixes such as "(m/w/d)" and "(H/F)" are ignored;
   - skills stay as they are, because tool names are the same in every language.
10. **(2026-10-21) The measurements changed 2b.2.** Matching is the cost and HTML cleaning isn't, so the plan is now the anchor-word prefilter plus the skill cache, without a description-text cache. The UDF stays a plain row-at-a-time Python UDF. A pandas (vectorised) UDF only cuts the transfer cost per row, which is small next to the 40 ms of regex work per job.
11. **(2026-10-21) The industry list is Jobicy's 22 plus 4 new ones** where nothing fits: Hardware & Electronics, Research & Science, Engineering & Manufacturing (non-software), and Logistics & Supply Chain. Two of the kept Himalayas Tech categories (Hardware Engineer, Research & Development) and many on-site Arbeitnow jobs need them.
12. **(2026-10-21) Arbeitnow tags map by exact value.** Only the generic tags are mapped: frequent ones, checked against sample job titles ("Credit Analysis" is really telesales, and "Security" is risk and compliance). The long tail of company department names gets no industry, and a checks warning reports the unmapped share.
13. **(2026-10-21) Job types follow the schedule:** Full-Time, Part-Time, Contract (freelance or contractor), Internship, plus **Temporary**. Contract-only values (permanent, fixed-term, CDI/CDD) give no job type unless a schedule value is listed too. Level-like values ("berufserfahren", "teamleitung", "Werkstudent") feed `levels.csv` instead.
14. **(2026-10-21) No `silver.ref_cities` table.** `cities.csv` (lowercased aliases) is read only by the Python location parser, which locates the few hundred distinct raw location strings per run. `countries.csv` becomes `silver.ref_countries`.
15. **(2026-10-21) Cities come from GeoNames `cities1000`, and a shared name goes to the European place first,** then the most populous. This changes decision 8. Measured on the 1,500 sampled Arbeitnow jobs:
    - unknown locations fell from 10.3% to 4.5%, and 2.6% of jobs have an empty location;
    - by population alone, 8 jobs landed outside Europe, because GeoNames also lists old and foreign names: Baden → South San Francisco, Sion → Jerusalem, Malakoff → Oued Sly in Algeria;
    - `cities.csv` grows from 205,652 to 599,326 aliases (18 MB).
16. **(2026-10-21) All three job DAGs run at 18:00 UTC.** The APIs are separate servers with their own limits, the DAGs only upload files, and starting together means they land within minutes of each other, ready for one `transform_jobs` run in Phase 4.
17. **(2026-10-21) Arbeitnow's `is_listed_now` means seen in either of its last two runs.** Each full download misses about 1% of the feed at random (see 2b.5). With one run, about 60 listed jobs a day would show as not listed; with two, a job only counts as gone when two runs in a row miss it (about 0.01%). The cost: a job really removed from the feed still shows as listed for one more day. Jobicy keeps "in the latest run", and Himalayas uses `expires_at`.
18. **(2026-10-21) Himalayas jobs are removed at `expiryDate`, from storage too.** This confirms decision 4 after reading the full API terms.
    - Clause 113(d) says: "Cache job data where you can, stay within your request limits, and remove jobs once they expire." It's a caching rule, so it's read as covering stored copies, not only what dashboards show. Landing files and bronze rows are purged too, followed by `VACUUM`.
    - The API docs add that jobs can close before `expiryDate` and suggest re-reading the feed daily. That's advice for mirrors and would take 6,422 requests a day, so a job taken down early stays until its `expiryDate`.
    - Real Himalayas jobs are never committed to the repo; the test fixture is made up.
19. **(2026-10-21) Himalayas' incremental state is a `manifest.json` in each run's folder,** written last. The next run reads the manifest of the finished run that saw the newest job. The state lives with the data: deleting the landed files makes the next run start over with 7 days. Rejected: an Airflow Variable (the state lives apart from the data) and a fixed 3-day window (misses jobs after a longer break).
20. **(2026-10-21) Himalayas jobs are landed in one file per expiry day, and the DAG purges landing from the first run.**
    - Files of mixed expiry dates can't lose only their expired jobs without being rewritten. Grouped by the UTC day the jobs expire (`expires_2026-12-19.json`), a whole file is deleted once that day is tomorrow or earlier: up to a day early, never late.
    - A `purge_expired` task in `ingest_himalayas` does this every run, alongside `fetch_and_land`, so landing complies from day one.
    - Bronze, with one row per file, follows the same rule in 2b.9.
    - Measured on the sample: `expiryDate` is `pubDate` + 60 days for 90% of jobs (the shortest Tech job had 52.7 days), so a run's jobs fall on a few expiry days.
21. **(2026-10-21) Himalayas' first run goes back 2 days, not 7, and catching up is capped at 7 days.** This changes decision 6.
    - The feed is busier than the 500-job sample suggested: about 3,300 jobs are updated a day (5,000 jobs within 1.7 days, 20,000 within 5.8). Uncached deep pages take about 1.9 s each, including the 1 s wait.
    - The first 7-day attempt failed after 31 minutes and about 950 pages, about 5.7 days back. A dropped connection came first, then a 503 that outlasted the session's retries (about a minute). `land` writes at the end, so the whole walk was lost.
    - Now: the first run is 2 days (about 330 pages, about 10 minutes). This source's session retries 8 times (about 6 minutes of waiting), a progress line is logged every 100 pages, and `MAX_PAGES` is 2,000.
    - Rejected: a resumable walk (more code) and keeping 7 days with patient retries (a late outage still loses about 40 minutes of work).
22. **(2026-10-22) Bronze retention for Himalayas: the same 1-day lead as landing, and a 1-day file retention.** `07_retention_himalayas.py` (task `retention_himalayas`, after `bronze_himalayas`) runs three steps:
    - `DELETE`s the rows whose expiry day in `file_path` is tomorrow or earlier;
    - `REORG TABLE … APPLY (PURGE)` rewrites the files that still hold deleted rows (a `DELETE` only marks them in a deletion vector);
    - `VACUUM`s with `delta.deletedFileRetentionDuration` = 1 day.

    A job is out of every query before it expires, and its bytes are gone about 1–2 days after. Time travel on this table reaches back only 1 day. Rejected: deleting 3 days ahead so the bytes go before expiry (jobs would leave silver early), and Delta's default 7-day retention (bytes kept for about 8 days after expiry). `silver_jobs` waits for `retention_himalayas`, so it never reads an expired row.
23. **(2026-10-22) Arbeitnow locations are split at `;`.** "Bristol; Cambridge" gives two `job_locations` rows, like Jobicy's comma lists. Only `;` splits: `/` and `-` also occur inside single places ("Lausanne / Hybrid / Remote", "Saint-Etienne").
24. **(2026-10-22) Arbeitnow checks.**
    - Unknown locations are a warning above 10% of Arbeitnow jobs (4.5% expected). They stay an error for Jobicy and Himalayas.
    - The shares of jobs without an industry or job type are info lines per source. About 41% and 52% are expected for Arbeitnow by design (decisions 12 and 13).
25. **(2026-10-22) Arbeitnow's "Engineering" and "Development" tags are left unmapped.**
    - On the first full silver run, Software Engineering skill coverage fell to 89.9%: Arbeitnow 81.9%, against Himalayas 93.2% and Jobicy 97.4%.
    - The cause was these two tags. For 515 and 66 jobs respectively they were the only Software Engineering tag. Behind them: software jobs ("AI Engineer", "DevOps Engineer") mixed with construction, plant and electrical engineering, and marketing or treasury traineeships.
    - Like "IT" and "Consulting" (decision 12), they're too broad to name one industry. Projected: Arbeitnow without an industry ~50%; SE coverage ~92% for Arbeitnow, ~93% overall.
    - Rejected: mapping "Engineering" to Engineering & Manufacturing (software jobs labelled non-software) and a title keyword rule (more to maintain, still guesses).
26. **(2026-10-22) ISO 3166 country names are aliases in `locations.csv`.**
    - Some Himalayas jobs use ISO short names, and split at their comma or parenthesis several landed on the wrong place: "Congo, The Democratic Republic of the" → a town in Brazil, "Viet Nam" → a village in Ukraine, "Korea, Republic of" → Koréa in Ivory Coast. Others came out unknown ("Russian Federation", "Åland Islands").
    - Every ISO 3166-1 short and common name was run through `Locator`; the 21 that didn't resolve to their country are now aliases. Source: `iso_3166-1.json` of the Debian iso-codes project, the list `pycountry` uses.
    - GeoNames' name for BQ had a trailing space: fixed in `countries.csv`, and the build script now strips names.

## How data flows in Phase 2b

```
ingest_jobicy     18:00 daily ─► landing/jobicy/     ─► bronze_jobicy    ──┐
ingest_arbeitnow  18:00 daily ─► landing/arbeitnow/  ─► bronze_arbeitnow ──┤
ingest_himalayas  18:00 daily ─► landing/himalayas/  ─► bronze_himalayas ──┼─► silver_jobs ─► silver_skills ─► checks
ingest_fx_rates   17:00 Mon–Fri ► landing/frankfurter/ ► bronze_fx ► silver_fx ┤                   (skill cache)
reference CSVs ──────────────────────────────────────► reference ────────────┘
                                                        retention_himalayas (after bronze_himalayas)
```

## Faster skill matching (2b.2)

**Measured first (2026-10-21, all 1,447 Jobicy jobs, locally):** `html_to_text` takes 0.33 s in total (0.23 ms per job), but `SkillMatcher.match` takes **58.7 s** (40.6 ms per job). It ran all 384 skills' regexes over every description, while a job mentions only a few. That changed the plan (decision 10).

**1. A prefilter in `SkillMatcher`.** Each skill's **anchors** are the first word of each of its aliases, lowercased ("Node.js" → `node`, ".NET" → `net`, "C++" → `c`). Each job's text is split into a set of words once. A skill whose anchors are all missing from that set can't match, so its regex is skipped.
- Results can't change: an alias can only match where its first word stands as a whole word in the text.
- A test compares the prefiltered and the full search on all rule and trap sentences.
- A prototype on all 1,447 real jobs gave **identical** results, **10.8× faster** (58.3 s → 5.4 s), with 29 of 384 regexes run per job on average.

**2. A persistent skill cache.**

| Cache table (persistent, **not** rebuilt) | Key | Version | Value |
|---|---|---|---|
| `silver.cache_job_skills` | `sha2(to_json(title, description_text, company_name))` | `SkillMatcher.matcher_version`: a hash of the `skills.csv` rows **and** the code of `transform/skills.py` | the matched skills (array of structs; an empty array for jobs without skills) |

Each run:
1. Find the keys of the current jobs that have no cache row for the current version.
2. Run the Python UDF **only on those**, and add the results with a plain `INSERT`. A cache row never changes (the same text and version always give the same result), so there's nothing for a `MERGE` to update.
3. Check that every current job has a cache row, then build `job_skills` with a plain SQL join to the cache.
4. Delete cache rows of older versions, and of texts no current job has any more.

Identical text across jobs or sources is processed once. This is the first silver table that persists between runs, a deliberate exception to "silver is rebuilt every run". `job_skills`, built from it, is still rebuilt, keeps its columns, and keeps `taxonomy_version` as the skill-list fingerprint.

**Dropped:** a cache for cleaned descriptions. `html_to_text` is too cheap to be worth a table.

**Result (2026-10-21), two Job runs straight after deploying:**

| `silver_skills` | Jobs matched | Matching time | Task duration |
|---|---|---|---|
| Before (2026-10-19, 1,447 jobs, no prefilter, no cache) | all, every run | — | 99–108 s |
| Run 1: new `matcher_version`, empty cache | 1,611 (all) | 12.7 s | 43 s |
| Run 2: warm cache | **0** | 2.0 s | 25 s |

All 7 tasks and every error check passed in both runs. What remains of the 25 s (startup, loading the matcher, the self-test and the summary queries) doesn't grow with the number of jobs.

## Reference data (2b.3)

| File | Rows | From |
|---|---|---|
| `countries.csv` | every ISO country: alpha-2 code, English name, region | GeoNames `countryInfo.txt`, continent → our regions, with explicit overrides (Middle East → Middle East & Africa; Mexico, Central America and the Caribbean → LATAM; Türkiye → Europe as today) |
| `cities.csv` | place name (plus Latin-script alternate names), city, country code, population; a shared name goes to the European place, then the most populous | GeoNames `cities1000` (places over 1,000 people), built by `scripts/build_geo_reference.py` |
| `locations.csv` | stays the **alias** table: the exact raw values sources use ("USA", "Anywhere", "EMEA", "Remote"), plus local country names (Deutschland, Nederland, Schweiz, Suisse, Österreich, España, Italia…) | hand-made, as now |
| `industries.csv` | `source, raw_value, industry`, mapping Himalayas `parentCategories` and Arbeitnow `tags` to Jobicy's 22 industries (Jobicy maps to itself); role-only tags such as "Team Leader" map to nothing | hand-made from the profiling |
| `job_types.csv` | `raw_value, job_type`, the multilingual values to Jobicy's job types | hand-made from the profiling |
| `levels.csv` | `source, raw_value, seniority`: Jobicy `jobLevel`, Himalayas `seniority` (highest wins; Manager → Lead), Arbeitnow level-like job types ("berufserfahren" → Mid, "Werkstudent" → Intern, "teamleitung" → Lead) | hand-made; replaces the Jobicy mapping hard-coded in `seniority.py` |

## Location parser (2b.4)

`transform/locations.py`: `Locator.locate(raw)` returns a `Place` (`location_name`, `location_type`, `country_code`, `region`). The type is city, country, region, worldwide or unknown.
1. The whole string is looked up as one name: a `locations.csv` alias, a country name, then a city alias ("Berlin", "USA", "Remote job").
2. Otherwise it's split into parts at `, ; | / & : ( )` and at a dash with spaces around it, and noise words are dropped ("Office", "HQ", "Hybrid", "Remote"…). The first city in the named country wins, else the country, else the first region.
   - "Utrecht, Utrecht, Nederland" → Utrecht
   - "UK - Remote" → United Kingdom
   - "London, Ontario, Canada" → Canada
3. Otherwise it's unknown, and the cleaned text is kept as the name.

**Result on the profiled samples (2026-10-21):**
- Himalayas: all 81 values are countries.
- Jobicy: all its values are aliases.
- Arbeitnow (1,500 jobs): city 87.7%, country 4.4%, worldwide 3.1%, region 0.3%, unknown 4.5%. The unknown ones are 2.6% empty, plus tiny places, a street ("Moorgate London") and non-places ("Hybrid").

Known limits:
- A name shared by two European places goes to the bigger one: Brest → Belarus, Emmen → Netherlands.
- When the town isn't listed, a region with the same name as a city counts as that city: "Kleindorf, Utrecht, Nederland" would give Utrecht.
- 3 of the 1,500 sampled jobs list several places ("Bristol; Cambridge"), and the parser returns the first. Splitting them is a 2b.8 choice.

## Arbeitnow ingestion (2b.5)

`ingestion/sources/arbeitnow/`:
- `client.py` asks for `?page=1, 2, 3…`, 2 seconds apart, until `links.next` is empty. It checks that `meta.current_page` is the page asked for, and stops after 60 pages.
- `land.py` writes one file per page. Its summary adds `distinct_jobs` and `remote_jobs`.
- The `ingest_arbeitnow` DAG runs daily at 18:00 UTC.

**First runs (2026-10-21):** two full downloads about 40 minutes apart, the first started by unpausing (`run_immediately`), the second by the 18:00 schedule. Each had 25 pages and 6,013 rows, from 2026-10-14 17:17 to 2026-10-21 17:17, with 703 remote jobs (11.7%).

| | Run 1 | Run 2 |
|---|---|---|
| Distinct jobs | 5,824 | 5,808 |
| Only in this run, though inside both runs' windows | 72 | 56 |

The page sizes and date ranges were identical, so the feed didn't change between the runs, only its order. Together the runs saw about 5,880 distinct jobs. Each download sees about 99% of them, and which 1% it misses changes from run to run. The likely cause is ties: many jobs share the same `created_at` second, and the API's order within a tie isn't stable, so paging by position repeats some jobs and skips others. Silver keeps one row per job, so the repeats don't matter. Decision 17 handles the misses.

## Himalayas ingestion (2b.6)

`ingestion/sources/himalayas/`:
- **`client.py`** walks the feed newest first, 20 jobs per request, 1 second apart (the key allows 60 a minute). It follows `nextCursor` until a page reaches a job last updated before the cutoff, or the feed ends. The API key goes in the `Authorization: Bearer` header, never in the URL, so it can't reach logs or error messages. Every job must have a numeric `pubDate` and `expiryDate`, and a date that looks like milliseconds stops the run instead of walking the whole feed.
- **`land.py`** decides the cutoff and keeps the Tech jobs updated since then. It writes them in one file per UTC expiry day (`expires_2026-12-19.json`, about 960 jobs and 5 MB each), skipping jobs that expire by tomorrow. Then it writes `manifest.json`: the cutoff and why, pages, jobs seen, Tech jobs, skipped jobs, files, and the newest and oldest `pubDate`.
- **`purge_expired()`** (also in `land.py`) deletes every landed `expires_*.json` whose day is tomorrow or earlier (decision 20). Manifests stay: they hold no job data, and the newest one is the incremental state.

| Situation | Cutoff |
|---|---|
| First run (no manifest anywhere) | now − 2 days |
| Normal run | the previous finished run's newest `pubDate` − 1 day |
| After a long break | never more than 7 days back |
| A run cleared in Airflow after it had finished | its own manifest's cutoff, so the rerun fetches the same range before replacing its files |

A run that fails midway writes no manifest, so the next run ignores it.

The `ingest_himalayas` DAG runs daily at 18:00 UTC: `ensure_landing_volume`, then `fetch_and_land` → `check_run`, with `purge_expired` running alongside so a failed fetch doesn't block deleting. It needs `HIMALAYAS_API_KEY` in the root `.env`. `check_run` fails when no Tech jobs were found: the cutoff always covers at least a day, so zero would mean the categories changed.

**Expected size (measured 2026-10-21, decision 21):** about 3,300 updated jobs a day, of which about 29% (~960) are Tech. A page takes about 1.9 s.

| Run | Pages | Tech jobs landed | Duration |
|---|---|---|---|
| Normal day or first run (2 days; on a normal day half the jobs are repeats that silver collapses) | about 330 | about 1,900 in 2–3 files of about 5 MB | about 10 minutes |
| Catching up after a break (at most 7 days) | about 1,200 | about 6,700 in about 8 files | about 40 minutes |

**First run (2026-10-21):**
- Attempt 1 (7 days back) failed after 31 minutes (decision 21).
- Attempt 2 (2 days back) walked 239 pages: 4,780 jobs from 2026-10-19 20:30 to 2026-10-21 18:26 UTC, about 2,500 a day.
- It landed 1,443 Tech jobs (30%) in 15 files, 9.2 MB in total:
  - three files (expiring 2026-12-18, -19 and -20) hold about 95% of the jobs;
  - twelve small files of 1 to ~50 jobs expire between 2026-10-23 and 12-16. Those are jobs updated without their expiry being reset, so they go sooner. The earliest is purged by the next run.

**Known limit:** 19% of jobs have no parent category and are left out. Their free-form `categories` show that a few of them are tech roles ("IT SAP Analyst", "Zoho Developer"), about 3–4% of all jobs.

**For 2b.7 and 2b.9:**
- The manifest sits next to the job files, so `bronze_himalayas` must load only `expires_*.json`.
- Bronze rows are deleted by the same rule as landing files: the expiry day in `file_path` is tomorrow or earlier.

## Bronze and retention (2b.7, 2b.9)

- **New tasks:** `bronze_arbeitnow` and `bronze_himalayas` run the same `01_bronze.py`. Its new `file_glob` parameter sets Auto Loader's `pathGlobFilter`, so Himalayas loads only `expires_*.json`.
- **Purge:** `retention_himalayas` runs `07_retention_himalayas.py` after it (decision 22).
- **Dependencies:** `silver_jobs` now waits for both.

**First run (2026-10-22):**
- `bronze.arbeitnow_raw` got 50 files (two runs of 25).
- `bronze.himalayas_raw` got 15 files and no manifest.
- `retention_himalayas` deleted the `expires_2026-10-23` row, leaving 14 files and 1,442 jobs (earliest expiry 2026-11-02).
- All error checks passed.

`VACUUM` removes a purged file from the second daily run after the purge.

## Silver changes (2b.8)

**As built (2026-10-22):**
- **Observations:** `04_silver_jobs.py` has one conform `SELECT` per source in the `observations` view, with the shared columns in the table at the top of the notebook.
- **Seniority:** each job's level values are mapped through `ref_levels`, and the highest (by `transform.seniority.LEVELS`) is `derive_seniority`'s fallback.
- **Locations:** the distinct raw values are located on the driver with `Locator` and joined back with `<=>`.
- **Schema of `silver.jobs`:**
  - new columns `expires_at` and `is_remote`;
  - `geo_raw` (string) became `locations_raw` (array);
  - `source_level` (string) became `source_levels`: the source's level values that `levels.csv` lists, as given.

**Checked on the warehouse before the first Job run** (read-only `SELECT`s of the new SQL on today's bronze):

| | Arbeitnow | Himalayas | Jobicy |
|---|---|---|---|
| Rows → distinct jobs | 12,026 → 5,880 | 1,442 → 1,442 | 6,838 → 1,875 |
| Missing a required field | 0 | 0 | 0 |
| With a source level | 2,931 | 1,442 | 813 |
| Without industry / job type | 2,396 / 3,083 | 0 / 11 | 0 / 0 |
| Distinct raw locations | 1,137 | 137 | 54 |

**First runs with all three sources (2026-10-22, after the 18:00 ingestion):**
- **Run 1:** one error check failed. 3 Himalayas locations were unknown and 3 more had landed on wrong places (decision 26). Software Engineering skill coverage dropped to 89.9% (decision 25).
- **Run 2, after both fixes:** every error check passed.

| | Arbeitnow | Himalayas | Jobicy |
|---|---|---|---|
| Jobs (silver = bronze) | 6,948 | 3,028 | 2,115 |
| Listed now | 6,947 | 3,028 | 1,189 |
| With at least 1 skill | 65.1% | 89.5% | 79.8% |
| Seniority Unspecified | 26.3% | 0.0% | 38.5% |
| Without an industry / a job type | 50.5% / 50.7% | 0.0% / 0.6% | 0.0% / 0.0% |
| Unknown location | 5.7% | 0 | 0 |

Software Engineering skill coverage: 93.4% overall. The only warning left is the known salary one: 7 jobs without a currency, and 2 in currencies the ECB doesn't publish.

**Planned:**

- **One conform `SELECT` per source**, combined with `UNION ALL` into `observations`, with the same columns in the same order. New columns:
  - `is_remote`;
  - `expires_at` (Himalayas only);
  - `locations_raw` (an array: Jobicy's comma list split, Himalayas' countries, Arbeitnow's single string);
  - `industries_raw`, `job_types_raw`, `levels_raw`.
- **Himalayas jobs with `expires_at` in the past are left out.** `is_listed_now` means:
  - Himalayas: `expires_at > now`;
  - Arbeitnow: present in either of its last two runs (decision 17);
  - Jobicy: present in its latest run.
- **Mappings by SQL joins to the new reference tables.** Locations are located once per **distinct** raw value with the tested Python parser, which only handles a few hundred values.
- **Salary:** new period factors `annual` = 1 and `fortnightly` = 26. Unpublished currencies (CLP, BGN) stay unconverted, as now.
- **Checks per source:**
  - the bronze/silver job counts per source (Himalayas net of expired jobs);
  - unknown locations: error for Jobicy and Himalayas, warning for Arbeitnow;
  - freshness per source;
  - **no expired Himalayas job in silver** (error).

## Repo layout additions

```
docs/phases/phase-2b-sources-and-caching.md
scripts/build_geo_reference.py          ← downloads GeoNames, writes countries.csv and cities.csv (run by hand)
databricks/reference/
    countries.csv, cities.csv           ← generated, GeoNames (CC BY 4.0)
    industries.csv, job_types.csv, levels.csv
databricks/notebooks/07_retention_himalayas.py
transform/locations.py                  ← parse and locate raw location strings
ingestion/sources/arbeitnow/            ← client.py, land.py
ingestion/sources/himalayas/            ← client.py, land.py (incremental state, category filter)
airflow/dags/ingest_arbeitnow.py, ingest_himalayas.py
tests/  test_skills.py (prefilter, matcher_version), test_locations.py, test_arbeitnow_*.py, test_himalayas_*.py, fixtures/ (trimmed real pages)
```

## Pitfalls

- **A cache can go stale:** that's why `matcher_version` includes the code (`skills.py`), not only the CSV. A rule change with an unchanged list would otherwise keep serving old matches.
- **Arbeitnow's page order isn't stable,** so even a full download repeats some jobs and misses about 1% (2b.5). Page sizes also shrink towards the end (300 … 250 … 150, 64), so stop when `links.next` is empty, not on a short page.
- **Himalayas' docs and real responses differ:** dates come in seconds, and `locationRestrictions` holds plain strings. Parse defensively, and test with real saved pages.
- **Deleting rows isn't removing data in Delta:** a `DELETE` keeps old versions for time travel. `VACUUM` removes the files after the retention period (7 days by default), so purged Himalayas jobs are gone from storage within about a week.
- **Comma meaning differs by source:** Jobicy's "Canada, USA" is a list of places, while Arbeitnow's "Utrecht, Utrecht, Nederland" is one place. Each conform `SELECT` has to produce the right array.
- **French "Stage" and English "stage"** ("early-stage startup"), German "Leiter" inside compounds ("Teamleiter" is Lead, "Abteilungsleiter" is Director), and Spanish/Italian "entra": each needs a trap test.
- **Cross-source duplicates:** Himalayas aggregates postings that may also be on Jobicy. They're kept as separate rows per source, as decided in Phase 2. Detecting them is out of scope here.
