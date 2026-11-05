-- Openings counted twice when agg_skill_weekly_trend adds the openings of Jobicy and Arbeitnow (recomputed from silver)
-- to those of Himalayas (frozen in hist_himalayas_*_by_day), per week: Jobicy/Arbeitnow openings + Himalayas openings -
-- openings over all boards (int_job_openings; Phase 5, decisions 12 and 13). The trend subtracts them, so a job on
-- several boards counts once per opening, in the week it began. A week is counted by the build that completes it, once
-- its Sunday is two days old (a margin for jobs a feed lists a day late), while the Himalayas postings are still in
-- silver: Himalayas deletes its jobs at expiry. The trend shows exactly the weeks stored here. The first build counts
-- every complete week from 2026-10-19; after that, each build appends the weeks completed since.
with weeks as (
  select distinct week_start
  from {{ ref('dim_date') }}
  where week_start >= date'2026-10-19'
    and week_start <= date_sub(current_date(), 8)
  {% if is_incremental() %}
    and week_start > (select coalesce(max(week_start), date'1970-01-01') from {{ this }})
  {% endif %}
),
counted_twice as (
  select
    week_start,
    count_if(scope = 'jobicy_arbeitnow') + count_if(scope = 'himalayas') - count_if(scope = 'all_boards') as jobs
  from {{ ref('int_job_openings') }}
  group by week_start
)
select w.week_start, coalesce(c.jobs, 0) as jobs
from weeks as w
left join counted_twice as c
  on c.week_start = w.week_start
