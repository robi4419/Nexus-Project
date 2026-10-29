select
  job_key, company_key, seniority, published_date,
  source, source_job_id, title, url, is_remote, is_listed_now, published_at,
  published_month, expires_at, first_seen_at, last_seen_at, times_seen,
  salary_min, salary_max, salary_currency, salary_period,
  salary_min_usd_yearly, salary_max_usd_yearly, salary_mid_usd_yearly, salary_is_plausible
from {{ ref('int_job_postings') }}