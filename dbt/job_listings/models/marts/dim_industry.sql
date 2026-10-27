with industries as (
  select distinct industry
  from {{ ref('stg_silver__job_industries') }}
)
select * from industries