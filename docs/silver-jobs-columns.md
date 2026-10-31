# `silver.jobs`: columns and how they're built

`silver.jobs` holds **one row per job posting** from three job APIs:
- **Jobicy:** remote jobs, worldwide;
- **Arbeitnow:** mostly on-site jobs in Europe;
- **Himalayas:** remote tech jobs.

The raw API responses are landed as JSON files, loaded into bronze tables unchanged, and conformed into this table every day by a Databricks Job. The code is in [`databricks/notebooks/04_silver_jobs.py`](../databricks/notebooks/04_silver_jobs.py); the text cleaning, seniority rules and location parser are in the [`transform/`](../transform) package. *As of 2026-10-26.*

## Which rows

- **One row per job:** the latest copy of each (`source`, `source_job_id`). A job seen in several daily downloads keeps its most recently landed version, with the run id as a tie-breaker.
- **Expired Himalayas jobs are left out.** Himalayas' API terms require removing jobs once they expire. The expiry filter runs *after* the latest copy is picked, so an older copy can't stand in for an expired job.

## Identity and links

| Column | Type | Jobicy | Arbeitnow | Himalayas |
|---|---|---|---|---|
| `source` | string | `'jobicy'` | `'arbeitnow'` | `'himalayas'` |
| `source_job_id` | string | `id` | `slug` | `guid` (the job's stable URL) |
| `url` | string | `url` | `url` (the Arbeitnow page) | `applicationLink` (Himalayas' terms: every Apply uses it) |
| `title` | string | `jobTitle` | `title` | `title` |
| `company_name` | string | `companyName` | `company_name` | `companyName` |
| `company_logo_url` | string | `companyLogo` | NULL | `companyLogo` |

`title` and `company_name` are copied as given. Some still contain HTML entities, a known limitation: about 80 Himalayas titles (e.g. `&#x2f;`) and 15 Jobicy company names (`&amp;`).

## Dates and status

| Column | Type | How it's built |
|---|---|---|
| `published_at` | timestamp | **Jobicy:** `pubDate`, text converted to a timestamp. **Arbeitnow:** `created_at`, Unix seconds. **Himalayas:** `pubDate`, Unix seconds, which is the job's *last update*, not its first publication. |
| `published_date` | date | `date(published_at)`, in UTC |
| `expires_at` | timestamp | **Himalayas:** `expiryDate`, Unix seconds. **Others:** NULL. |
| `is_remote` | boolean | **Jobicy and Himalayas:** always `true` (remote-only feeds). **Arbeitnow:** its `remote` flag. |
| `is_listed_now` | boolean | **Jobicy:** the job is in Jobicy's latest download. **Arbeitnow:** in either of its last two downloads, because one Arbeitnow download misses about 1% of the feed at random. **Himalayas:** `expires_at` is after the build time (Himalayas is fetched incrementally, so "in the latest download" doesn't apply). |

## History and build

| Column | Type | How it's built |
|---|---|---|
| `first_seen_at` | timestamp | the earliest `landed_at` among all copies of the job, i.e. when a file containing it was first landed |
| `last_seen_at` | timestamp | the latest `landed_at` among its copies |
| `times_seen` | bigint | the number of distinct downloads (runs) that contained the job |
| `built_at` | timestamp | `current_timestamp()` when the table was built. It's the same for every row, and freshness checks use it. |

## Seniority

| Column | Type | How it's built |
|---|---|---|
| `source_levels` | array of strings | The job's own level values that the mapping file `levels.csv` lists for its source, as given, deduplicated and sorted. **Jobicy:** `[jobLevel]`. **Arbeitnow:** the level-like values among its `job_types` and `tags`, e.g. "berufserfahren" (experienced) or "Team Leader". **Himalayas:** `seniority`. It's an empty array, never NULL, when there are none. |
| `seniority` | string | **1.** Rules on the job title, in English, German, French and Dutch, with traps such as "Account Executive" (a sales role, not an executive). **2.** Otherwise a fallback: the highest of `source_levels`, mapped to our scale through `levels.csv`. The scale is Intern < Junior < Mid < Senior < Lead < Director < Executive. Values reviewed as unreliable, such as Jobicy's "Director" and "Any", map to nothing. **3.** Otherwise `'Unspecified'`. Never NULL. |
| `seniority_source` | string | where `seniority` came from: `'title'`, `'source_level'` or `'none'` |

## Location

| Column | Type | How it's built |
|---|---|---|
| `locations_raw` | array of strings | **Jobicy:** `jobGeo` split at `,` and trimmed ("USA, Canada"). **Arbeitnow:** `location` split at `;` ("Bristol; Cambridge"); an empty location stays one empty entry. **Himalayas:** `locationRestrictions` (country names), or `['Worldwide']` when empty. |

This column keeps only the raw values. The located places are in **`silver.job_locations`**, one row per value, with place name, type (city, country, region, worldwide or unknown), country code and region. They come from a parser that uses hand-made aliases, GeoNames countries and GeoNames places with over 1,000 inhabitants.

## Text

| Column | Type | How it's built |
|---|---|---|
| `excerpt` | string | **Jobicy:** `jobExcerpt`. **Himalayas:** `excerpt`. **Arbeitnow:** NULL. |
| `description_text` | string | The posting's HTML description cleaned to plain text: block tags become line breaks, other tags are removed, entities like `&amp;` are decoded, and whitespace is collapsed. Skills are extracted from this text and the title. |

## Salary

| Column | Type | How it's built |
|---|---|---|
| `salary_min`, `salary_max` | double | As given. **Jobicy:** `salaryMin`, `salaryMax`. **Himalayas:** `minSalary`, `maxSalary`. **Arbeitnow:** NULL (it publishes no salaries). |
| `salary_currency` | string | **Jobicy:** `salaryCurrency`. **Himalayas:** `currency`. **Arbeitnow:** NULL. |
| `salary_period` | string | **Jobicy and Himalayas:** `salaryPeriod`. **Arbeitnow:** NULL. |
| `fx_rate_date` | date | The date of the exchange rate used: the **latest ECB rate on or before `published_date`** for the salary's currency, from `silver.fx_rates` (an *as-of join*). NULL when there's no salary, no currency, or no ECB rate for the currency (e.g. CLP, BGN). |
| `salary_min_usd_yearly`, `salary_max_usd_yearly` | double | **amount × yearly factor × USD per unit of the currency** |

The yearly factor depends on `salary_period`:
- yearly or annual: 1;
- monthly: 12;
- fortnightly: 26;
- weekly: 52;
- daily: 260;
- hourly: 2,080.

A missing period counts as yearly. An unknown period, or a currency without a rate, gives NULL.

There's **no plausibility check** at this layer: implausible values, such as an "hourly" salary of 47,840, pass through. The gold layer flags them.

## Conformed, but not stored in this table

Three more fields are unified per source in the same step, but they feed other tables instead of becoming columns here:

| Field | Jobicy | Arbeitnow | Himalayas | Feeds |
|---|---|---|---|---|
| `levels_raw` | `[jobLevel]` | `job_types` + `tags` | `seniority` | `source_levels` and `seniority` (above) |
| `industries_raw` | `jobIndustry` | `tags` | `parentCategories`; without any, the title's Tech category (`transform/tech_titles.py`) | `silver.job_industries`, mapped through `industries.csv` |
| `job_types_raw` | `jobType` | `job_types` | `[employmentType]` | `silver.job_types`, mapped through `job_types.csv` |

## Which columns can be NULL

- **Always filled:** `source`, `source_job_id`, `url`, `title`, `company_name`, `published_at`, `published_date`, `is_remote`, `seniority`, `seniority_source`, `source_levels`, `is_listed_now`, `first_seen_at`, `last_seen_at`, `times_seen`, `built_at`.
- **NULL for a whole source:**
  - `company_logo_url` and `excerpt`: Arbeitnow;
  - `expires_at`: Jobicy and Arbeitnow;
  - all salary and exchange-rate columns: Arbeitnow.
- **NULL for some jobs:** the salary and exchange-rate columns, when a posting has no salary or its currency has no ECB rate. `locations_raw` too, in the rare Jobicy job without `jobGeo`.
