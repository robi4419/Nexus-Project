-- The same jobs as hist_himalayas_jobs_by_day, counted per day first seen x skill, with the skills of all the job's
-- postings. counted_through is the latest first_seen_at over all the jobs read, with or without skills.
with himalayas_jobs as (
  select job_key, min(first_seen_at) as first_seen_at
  from {{ ref('int_job_postings') }}
  where source = 'himalayas'
  group by job_key
),
new_jobs as (
  select job_key, first_seen_at
  from himalayas_jobs
  {% if is_incremental() %}
    where first_seen_at > (select coalesce(max(counted_through), timestamp'1970-01-01') from {{ this }})
  {% endif %}
),
batch as (
  select max(first_seen_at) as counted_through
  from new_jobs
)
select to_date(n.first_seen_at) as first_seen_date, js.skill, count(*) as jobs, b.counted_through
from new_jobs as n
join {{ ref('int_job_skills') }} as js
  on n.job_key = js.job_key
cross join batch as b
group by to_date(n.first_seen_at), js.skill, b.counted_through
