-- Per day first seen, silver may hold fewer Himalayas jobs than the frozen history (expired ones leave silver), but
-- never more: those would be jobs the history missed.
with silver as (
  select to_date(first_seen_at) as first_seen_date, count(*) as silver_jobs
  from {{ ref('stg_silver__jobs') }}
  where source = 'himalayas'
  group by to_date(first_seen_at)
),
history as (
  select first_seen_date, sum(jobs) as counted_jobs
  from {{ ref('hist_himalayas_jobs_by_day') }}
  group by first_seen_date
)
select s.first_seen_date, s.silver_jobs, coalesce(h.counted_jobs, 0) as counted_jobs
from silver as s
left join history as h
  on s.first_seen_date = h.first_seen_date
where s.silver_jobs > coalesce(h.counted_jobs, 0)
