with source as (
  select * from {{ source('silver', 'industry_labels') }}
),
renamed as (
  select job_key, industry, split, unsure
  from source
)
select * from renamed
