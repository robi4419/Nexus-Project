select distinct job_key, location_key
from {{ ref('stg_silver__job_locations') }}