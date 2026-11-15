with source as (
  select * from {{ source('silver', 'job_industry_predictions') }}
),
renamed as (
  select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as posting_key,
    industry, industry_probability, industry_group, group_probability, model_version
  from source
)
select * from renamed
