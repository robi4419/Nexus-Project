-- The openings of hist_himalayas_overlap_jobs_by_week per week x skill, with the skills of all the job's postings.
-- Counts the weeks that model has stored and this one hasn't yet, so both freeze the same weeks.
with weeks as (
  select week_start
  from {{ ref('hist_himalayas_overlap_jobs_by_week') }}
  {% if is_incremental() %}
    where week_start > (select coalesce(max(week_start), date'1970-01-01') from {{ this }})
  {% endif %}
),
counted_twice as (
  select
    o.week_start,
    js.skill,
    count_if(o.scope = 'jobicy_arbeitnow') + count_if(o.scope = 'himalayas') - count_if(o.scope = 'all_boards')
      as jobs
  from {{ ref('int_job_openings') }} as o
  join weeks as w
    on o.week_start = w.week_start
  join {{ ref('int_job_skills') }} as js
    on o.job_key = js.job_key
  group by o.week_start, js.skill
)
select week_start, skill, jobs
from counted_twice
where jobs > 0
