select job_key, industry
from {{ ref('stg_silver__job_industries') }}