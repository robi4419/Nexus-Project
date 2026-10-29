with skills as (
  select * from {{ ref('stg_silver__ref_skills') }}
)
select * from skills