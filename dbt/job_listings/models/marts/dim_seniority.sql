with levels as (
  select * from {{ ref('seniority_levels') }}
)
select * from levels