-- Kept only until the report reads fct_job_postings.industry (Phase 5, task 5.12, step 6): one row per job.
select job_key, industry
from {{ ref('fct_job_postings') }}
