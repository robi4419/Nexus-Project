-- Silver may hold fewer Himalayas jobs than the frozen history (expired ones leave silver), but never more: those would
-- be jobs the history missed. Compared as running totals by day first seen: a job whose earliest posting expired moves
-- to the day its next posting was first seen, while the history counted it on the earlier day.
with silver_jobs as (
  select job_key, min(first_seen_at) as first_seen_at
  from {{ ref('int_job_postings') }}
  where source = 'himalayas'
  group by job_key
),
silver as (
  select to_date(first_seen_at) as first_seen_date, count(*) as silver_jobs
  from silver_jobs
  group by to_date(first_seen_at)
),
history as (
  select first_seen_date, sum(jobs) as counted_jobs
  from {{ ref('hist_himalayas_jobs_by_day') }}
  group by first_seen_date
),
days as (
  select
    coalesce(s.first_seen_date, h.first_seen_date) as first_seen_date,
    coalesce(s.silver_jobs, 0) as silver_jobs,
    coalesce(h.counted_jobs, 0) as counted_jobs
  from silver as s
  full join history as h
    on s.first_seen_date = h.first_seen_date
),
running as (
  select
    first_seen_date,
    sum(silver_jobs) over (order by first_seen_date) as silver_so_far,
    sum(counted_jobs) over (order by first_seen_date) as counted_so_far
  from days
)
select first_seen_date, silver_so_far, counted_so_far
from running
where silver_so_far > counted_so_far
