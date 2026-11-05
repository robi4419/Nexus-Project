-- One row per job x skill: the skills of all the job's postings, so a job posted several times counts once.
with postings as (
  select posting_key, job_key from {{ ref('int_job_postings') }}
),
posting_skills as (
  select * from {{ ref('stg_silver__job_skills') }}
)
select p.job_key, ps.skill, max(ps.mentions) as mentions, bool_or(ps.in_title) as in_title
from posting_skills as ps
join postings as p
  on ps.posting_key = p.posting_key
group by p.job_key, ps.skill
