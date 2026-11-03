with jobs as (
  select * from {{ ref('fct_job_postings') }}
),
job_skills as (
  select * from {{ ref('int_job_skills') }}
)
select
  js.job_key, js.skill, js.mentions, js.in_title,
  j.published_date, j.company_key, j.seniority, j.is_listed_now, j.is_remote
from jobs as j
join job_skills as js
  on j.job_key = js.job_key
