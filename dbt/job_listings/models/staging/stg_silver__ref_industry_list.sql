with source as (
  select * from {{ source('silver', 'ref_industry_list') }}
),
renamed as (
  select industry, industry_group, cast(sort_order as int) as sort_order
  from source
)
select * from renamed
