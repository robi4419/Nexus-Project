{{ config(severity='warn') }}

with salaries as (
  select
    count_if(not salary_is_plausible) as implausible,
    count(salary_is_plausible) as salaried
  from {{ ref('fct_job_postings') }}
)
select implausible, salaried, try_divide(implausible, salaried) as implausible_share
from salaries
where try_divide(implausible, salaried) > {{ var('max_implausible_salary_share') }}