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
select p.location_key, p.location_name, p.location_type, p.country_code,
  coalesce(p.region, '(unknown)') as region,
  case
    when p.country_code is not null then c.country_name
    when p.location_type = 'region' then concat('(', p.location_name, ')')
    when p.location_type = 'worldwide' then '(anywhere)'
    else '(unknown)'
  end as country_name,
  case p.location_type
    when 'city' then p.location_name
    when 'country' then '(whole country)'
    when 'region' then concat('(', p.location_name, ')')
    when 'worldwide' then '(anywhere)'
    else '(unknown)'
  end as city_name
from places as p
left join countries as c
  on p.country_code = c.country_code
  