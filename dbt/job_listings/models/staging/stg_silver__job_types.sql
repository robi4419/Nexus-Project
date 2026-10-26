with source as (
  select * from {{ source('silver', 'job_types') }}
),
renamed as (
  select {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as job_key, job_type
  from source
)
select * from renamed