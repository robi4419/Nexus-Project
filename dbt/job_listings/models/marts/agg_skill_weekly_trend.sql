with weeks as (
  select distinct week_start from {{ ref('dim_date') }}
  where week_start >= date'2026-10-19'
    and week_start <= date_sub(current_date(), 8)
),
grid as (
  select week_start, skill
  from weeks
  cross join {{ ref('dim_skill') }}
),
postings as (
  select job_key, week_start
  from {{ ref('fct_job_postings') }} as jp
  join {{ ref('dim_date') }} as d
    on jp.published_date = d.date_day
  where source in ('jobicy', 'arbeitnow')
),
week_totals as (
  select week_start, count(*) as week_jobs
  from postings
  group by week_start
),
skill_counts as (
  select week_start, skill, count(*) as jobs
  from postings as p
  join {{ ref('fct_job_skills') }} as js
    on p.job_key = js.job_key
  group by week_start, skill
),
weekly as (
  select grid.week_start, grid.skill, coalesce(sc.jobs, 0) as jobs, wt.week_jobs, coalesce(sc.jobs, 0)/wt.week_jobs as share
  from grid
  join week_totals as wt
    on grid.week_start = wt.week_start
  left join skill_counts as sc
    on grid.week_start = sc.week_start
    and grid.skill = sc.skill
)
select weekly.*,
  lag(jobs) over (partition by skill order by week_start) as prev_jobs,
  lag(share) over (partition by skill order by week_start) as prev_share,
  share - lag(share) over (partition by skill order by week_start) as share_change
from weekly