-- One row per job: as many rows as int_job_postings has distinct job_key values, none lost or duplicated.
with expected as (
  select count(distinct job_key) as jobs from {{ ref('int_job_postings') }}
),
actual as (
  select count(*) as jobs from {{ ref('fct_job_postings') }}
)
select e.jobs as expected_jobs, a.jobs as actual_jobs
from expected as e
cross join actual as a
where e.jobs <> a.jobs
