-- Jobicy and Arbeitnow keep every job in silver: count them by the week they were published.
with silver_postings as (
  select jp.job_key, jp.source, d.week_start
  from {{ ref('fct_job_postings') }} as jp
  join {{ ref('dim_date') }} as d
    on jp.published_date = d.date_day
  where jp.source in ('jobicy', 'arbeitnow')
),
silver_week_totals as (
  select source, week_start, count(*) as week_jobs
  from silver_postings
  group by source, week_start
),
silver_skill_counts as (
  select p.source, p.week_start, js.skill, count(*) as jobs
  from silver_postings as p
  join {{ ref('fct_job_skills') }} as js
    on p.job_key = js.job_key
  group by p.source, p.week_start, js.skill
),
-- Himalayas deletes expired jobs: count it from the frozen daily counts, by the week each job was first seen.
himalayas_week_totals as (
  select 'himalayas' as source, d.week_start, sum(h.jobs) as week_jobs
  from {{ ref('hist_himalayas_jobs_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  group by d.week_start
),
himalayas_skill_counts as (
  select 'himalayas' as source, d.week_start, h.skill, sum(h.jobs) as jobs
  from {{ ref('hist_himalayas_skills_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  group by d.week_start, h.skill
),
week_totals as (
  select source, week_start, week_jobs from silver_week_totals
  union all
  select source, week_start, week_jobs from himalayas_week_totals
),
skill_counts as (
  select source, week_start, skill, jobs from silver_skill_counts
  union all
  select source, week_start, skill, jobs from himalayas_skill_counts
),
-- complete weeks only: a week counts once its Sunday is a day old
grid as (
  select wt.week_start, wt.source, s.skill, wt.week_jobs
  from week_totals as wt
  cross join {{ ref('dim_skill') }} as s
  where wt.week_start >= date'2026-10-19'
    and wt.week_start <= date_sub(current_date(), 8)
),
weekly as (
  select grid.week_start, grid.source, grid.skill, coalesce(sc.jobs, 0) as jobs, grid.week_jobs,
    coalesce(sc.jobs, 0) / grid.week_jobs as share
  from grid
  left join skill_counts as sc
    on grid.source = sc.source
    and grid.week_start = sc.week_start
    and grid.skill = sc.skill
)
select weekly.*,
  lag(jobs) over (partition by source, skill order by week_start) as prev_jobs,
  lag(share) over (partition by source, skill order by week_start) as prev_share,
  share - lag(share) over (partition by source, skill order by week_start) as share_change
from weekly
