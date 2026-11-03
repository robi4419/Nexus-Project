select distinct job_key, source
from {{ ref('int_job_postings') }}
