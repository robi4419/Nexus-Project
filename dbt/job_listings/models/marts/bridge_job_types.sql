select job_key, job_type
from {{ ref('stg_silver__job_types') }}