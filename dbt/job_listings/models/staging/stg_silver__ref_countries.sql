with source as (
  select * from {{ source('silver', 'ref_countries') }}
),
renamed as (
  select country_code, country_name, region
  from source
)
select * from renamed