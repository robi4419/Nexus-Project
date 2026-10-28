with locations as (
  select * from {{ ref('stg_silver__job_locations') }}
),
places as (
  select distinct location_key, location_name, location_type, country_code, region
  from locations
),
countries as (
  select * from {{ ref('stg_silver__ref_countries') }}
)
select p.*, c.country_name
from places as p
left join countries as c
  on p.country_code = c.country_code
  