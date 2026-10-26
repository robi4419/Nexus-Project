with source as (
  select * from {{ source('silver', 'job_locations') }}
),
renamed as (
  select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as job_key,
    location_raw, location_name, location_type, country_code, region
  from source
)
select * from renamed