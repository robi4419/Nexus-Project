-- One row per job: the postings of one company and title (or description) merged, on any board (Phase 5, decision 11).
with postings as (
  select * from {{ ref('int_job_postings') }}
),
ranked as (
  select
    *,
    -- the posting that speaks for the job: a listed one if any, the newest first
    row_number() over (
      partition by job_key order by is_listed_now desc, published_at desc, posting_key
    ) as listing_rank,
    -- the posting whose salary the job shows: the newest plausible one, else the newest with any salary
    row_number() over (
      partition by job_key
      order by case when salary_is_plausible then 0 when not salary_is_plausible then 1 else 2 end,
        published_at desc, posting_key
    ) as salary_rank
  from postings
),
jobs as (
  select
    job_key,
    min(published_date) as published_date,
    min(published_at) as published_at,
    max(expires_at) as expires_at,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    bool_or(is_remote) as is_remote,
    bool_or(is_listed_now) as is_listed_now,
    count(*) as postings
  from postings
  group by job_key
)
select
  j.job_key, l.company_key, l.seniority, j.published_date,
  l.title, l.url, j.is_remote, j.is_listed_now, j.published_at,
  trunc(j.published_date, 'MM') as published_month, j.expires_at, j.first_seen_at, j.last_seen_at, j.postings,
  s.salary_min, s.salary_max, s.salary_currency, s.salary_period,
  s.salary_min_usd_yearly, s.salary_max_usd_yearly, s.salary_mid_usd_yearly, s.salary_is_plausible
from jobs as j
join ranked as l
  on l.job_key = j.job_key
  and l.listing_rank = 1
join ranked as s
  on s.job_key = j.job_key
  and s.salary_rank = 1
