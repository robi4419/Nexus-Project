select distinct p.job_key, l.location_key
from {{ ref('stg_silver__job_locations') }} as l
join {{ ref('int_job_postings') }} as p
  on l.posting_key = p.posting_key
