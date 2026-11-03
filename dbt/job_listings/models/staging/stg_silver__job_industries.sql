with source as (
  select * from {{ source('silver', 'job_industries') }}
),
renamed as (
  select {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as posting_key, industry
  from source
)
select * from renamed
