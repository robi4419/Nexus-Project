-- The same jobs as hist_himalayas_jobs_by_day, counted per day first seen x skill. counted_through is the latest
-- first_seen_at over all the jobs read, with or without skills.
with new_jobs as (
  select job_key, first_seen_at
  from {{ ref('stg_silver__jobs') }}
  where source = 'himalayas'
  {% if is_incremental() %}
    and first_seen_at > (select coalesce(max(counted_through), timestamp'1970-01-01') from {{ this }})
  {% endif %}
),
batch as (
  select max(first_seen_at) as counted_through
  from new_jobs
)
select to_date(n.first_seen_at) as first_seen_date, js.skill, count(*) as jobs, b.counted_through
from new_jobs as n
join {{ ref('stg_silver__job_skills') }} as js
  on n.job_key = js.job_key
cross join batch as b
group by to_date(n.first_seen_at), js.skill, b.counted_through
