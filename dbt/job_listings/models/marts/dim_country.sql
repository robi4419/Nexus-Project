with countries as (
  select * from {{ ref('stg_silver__ref_countries') }}
)
select * from countries