with source as (
  select * from {{ source('silver', 'ref_skills') }}
),
renamed as (
  select skill, category, taxonomy_version
  from source
)
select * from renamed