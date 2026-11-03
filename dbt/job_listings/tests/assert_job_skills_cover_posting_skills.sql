-- Every skill found in a posting reaches the posting's job in fct_job_skills. Returns the posting x skill rows that don't.
select ps.posting_key, ps.skill
from {{ ref('stg_silver__job_skills') }} as ps
left join {{ ref('int_job_postings') }} as p
  on ps.posting_key = p.posting_key
left join {{ ref('fct_job_skills') }} as js
  on js.job_key = p.job_key
  and js.skill = ps.skill
where js.job_key is null
