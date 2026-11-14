{{ config(severity='warn') }}

with waiting as (
  select count(*) as labels_waiting
  from {{ ref('stg_silver__industry_labels') }} as l
  left anti join {{ ref('fct_job_postings') }} as f
    on f.job_key = l.job_key
)
select labels_waiting
from waiting
where labels_waiting > 0
