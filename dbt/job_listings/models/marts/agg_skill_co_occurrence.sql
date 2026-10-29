with pairs as (
  select skill_a, skill_b, count(*) as jobs_both
  from {{ ref('int_job_skill_pairs') }}
  group by skill_a, skill_b
  having count(*) >= 5
),
both_directions as (
  select skill_a as skill, skill_b as co_skill, jobs_both from pairs
  union all
  select skill_b as skill, skill_a as co_skill, jobs_both from pairs
),
skill_jobs as (
  select skill, count(*) as skill_jobs
  from {{ ref('fct_job_skills') }}
  group by skill
),
total as (
  select count(distinct job_key) as jobs_with_skills from {{ ref('fct_job_skills') }}
)
select bd.skill, bd.co_skill, bd.jobs_both, sj1.skill_jobs, sj2.skill_jobs as co_skill_jobs,
  bd.jobs_both / sj1.skill_jobs as share_of_skill_jobs,
  bd.jobs_both * total.jobs_with_skills / (sj1.skill_jobs * sj2.skill_jobs) as lift
from both_directions as bd
join skill_jobs as sj1
  on bd.skill = sj1.skill
join skill_jobs as sj2
  on bd.co_skill = sj2.skill
cross join total
