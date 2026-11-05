-- One row per complete week x skill (Phase 5, decisions 12 and 13). A job counts once per opening, in the week the
-- opening began on any board (int_job_openings): a repost while one of its listings is still live doesn't count again.
-- A week's jobs are:
--   the openings Jobicy or Arbeitnow began that week, counted from silver, which keeps their postings;
-- + the openings Himalayas began that week, from the frozen counts, because it deletes expired jobs (decision 4);
-- - the openings those two count twice, frozen when the week was complete.
-- The weeks are those hist_himalayas_overlap_jobs_by_week has stored.
with jobicy_arbeitnow_jobs as (
  select job_key, week_start
  from {{ ref('int_job_openings') }}
  where scope = 'jobicy_arbeitnow'
),
week_parts as (
  select week_start, count(*) as jobs
  from jobicy_arbeitnow_jobs
  group by week_start
  union all
  select d.week_start, h.jobs
  from {{ ref('hist_himalayas_jobs_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  union all
  select week_start, -jobs
  from {{ ref('hist_himalayas_overlap_jobs_by_week') }}
),
skill_parts as (
  select ja.week_start, js.skill, count(*) as jobs
  from jobicy_arbeitnow_jobs as ja
  join {{ ref('int_job_skills') }} as js
    on ja.job_key = js.job_key
  group by ja.week_start, js.skill
  union all
  select d.week_start, h.skill, h.jobs
  from {{ ref('hist_himalayas_skills_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  union all
  select week_start, skill, -jobs
  from {{ ref('hist_himalayas_overlap_skills_by_week') }}
),
week_totals as (
  select frozen.week_start, sum(wp.jobs) as week_jobs
  from {{ ref('hist_himalayas_overlap_jobs_by_week') }} as frozen
  join week_parts as wp
    on wp.week_start = frozen.week_start
  group by frozen.week_start
),
-- frozen and live skill tags can differ by a job after an expiry or a matcher change; a count never goes below 0
skill_counts as (
  select week_start, skill, greatest(sum(jobs), 0) as jobs
  from skill_parts
  group by week_start, skill
),
grid as (
  select wt.week_start, s.skill, wt.week_jobs
  from week_totals as wt
  cross join {{ ref('dim_skill') }} as s
),
weekly as (
  select grid.week_start, grid.skill, coalesce(sc.jobs, 0) as jobs, grid.week_jobs,
    coalesce(sc.jobs, 0) / grid.week_jobs as share
  from grid
  left join skill_counts as sc
    on grid.week_start = sc.week_start
    and grid.skill = sc.skill
)
select
  weekly.*,
  lag(jobs) over (partition by skill order by week_start) as prev_jobs,
  lag(share) over (partition by skill order by week_start) as prev_share,
  share - lag(share) over (partition by skill order by week_start) as share_change
from weekly
