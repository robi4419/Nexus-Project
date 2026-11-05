with source as (
  select * from {{ source('silver', 'job_skills') }}
),
renamed as (
  select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as posting_key,
    skill, category, mentions, in_title, taxonomy_version
  from source
)
select * from renamed
