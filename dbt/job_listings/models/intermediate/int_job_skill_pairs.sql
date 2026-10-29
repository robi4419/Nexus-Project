with job_skills as (
  select * from {{ ref('stg_silver__job_skills') }}
),
final as (
  select a.job_key, a.skill as skill_a, b.skill as skill_b
  from job_skills as a
  join job_skills as b
    on a.job_key = b.job_key
    and a.skill < b.skill
)
select * from final