select distinct p.job_key, i.industry
from {{ ref('stg_silver__job_industries') }} as i
join {{ ref('int_job_postings') }} as p
  on i.posting_key = p.posting_key
