-- Himalayas jobs first seen since the previous build, counted per day. The first build counts every Himalayas job in
-- silver; after that, is_incremental() keeps only jobs first seen after the latest counted_through already stored.
with new_jobs as (
  select job_key, first_seen_at
  from {{ ref('stg_silver__jobs') }}
  where source = 'himalayas'
  {% if is_incremental() %}
    and first_seen_at > (select coalesce(max(counted_through), timestamp'1970-01-01') from {{ this }})
  {% endif %}
),
batch as (
  select max(first_seen_at) as counted_through
  from new_jobs
)
select to_date(n.first_seen_at) as first_seen_date, count(*) as jobs, b.counted_through
from new_jobs as n
cross join batch as b
group by to_date(n.first_seen_at), b.counted_through
