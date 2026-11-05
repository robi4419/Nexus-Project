select distinct p.job_key, t.job_type
from {{ ref('stg_silver__job_types') }} as t
join {{ ref('int_job_postings') }} as p
  on t.posting_key = p.posting_key
