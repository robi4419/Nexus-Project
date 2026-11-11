-- One row per complete week x board x skill (Phase 5, decision 14): the openings that began on the board that week, and
-- those asking for the skill. Jobicy and Arbeitnow are counted from silver, through their own scopes in int_job_openings;
-- Himalayas from the frozen counts in hist_himalayas_*_by_day, because it deletes expired jobs (decision 4). A job on
-- several boards counts on each. The weeks are those hist_himalayas_overlap_jobs_by_week has stored, as for
-- agg_skill_weekly_trend. Every board and skill has a row each week, 0 when it had no jobs.
with weeks as (
  select week_start from {{ ref('hist_himalayas_overlap_jobs_by_week') }}
),
boards as (
  select board from values ('jobicy'), ('arbeitnow'), ('himalayas') as t(board)
),
listed_openings as (
  select job_key, scope as board, week_start
  from {{ ref('int_job_openings') }}
  where scope in ('jobicy', 'arbeitnow')
),
board_jobs as (
  select board, week_start, count(*) as jobs
  from listed_openings
  group by board, week_start
  union all
  select 'himalayas' as board, d.week_start, sum(h.jobs) as jobs
  from {{ ref('hist_himalayas_jobs_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  group by d.week_start
),
skill_jobs as (
  select o.board, o.week_start, js.skill, count(*) as jobs
  from listed_openings as o
  join {{ ref('int_job_skills') }} as js
    on js.job_key = o.job_key
  group by o.board, o.week_start, js.skill
  union all
  select 'himalayas' as board, d.week_start, h.skill, sum(h.jobs) as jobs
  from {{ ref('hist_himalayas_skills_by_day') }} as h
  join {{ ref('dim_date') }} as d
    on h.first_seen_date = d.date_day
  group by d.week_start, h.skill
)
select
  w.week_start,
  b.board,
  s.skill,
  coalesce(sj.jobs, 0) as skill_jobs,
  coalesce(bj.jobs, 0) as board_jobs
from weeks as w
cross join boards as b
cross join {{ ref('dim_skill') }} as s
left join board_jobs as bj
  on bj.week_start = w.week_start
  and bj.board = b.board
left join skill_jobs as sj
  on sj.week_start = w.week_start
  and sj.board = b.board
  and sj.skill = s.skill
