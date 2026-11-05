-- One row per job x scope x week in which an opening of the job began (Phase 5, decisions 12 and 13). Each posting is a
-- listing: Jobicy and Arbeitnow on its publish date, Himalayas on the day it was first seen. A listing starts a new
-- opening when none of the job's earlier listings is still live, so a repost while one is live is the same opening and a
-- later one is a new opening. A Jobicy or Arbeitnow listing counts as live for 8 weeks (their feeds show only 7 days, so
-- we can't see when a job closes); a Himalayas one until it expires, a median of 59 days, which is also when the
-- Himalayas history counts a job again. The scopes: jobicy_arbeitnow and himalayas look only at that board group's
-- listings, all_boards at every listing. The weekly trend adds the first two and subtracts what they count twice.
with listings as (
  select
    job_key,
    source,
    case when source = 'himalayas' then to_date(first_seen_at) else published_date end as listed_date,
    -- exclusive: an earlier listing m blocks a listing l when m.listed_date < l.listed_date < m.live_until
    case when source = 'himalayas' then to_date(expires_at) else date_add(published_date, 56) end as live_until
  from {{ ref('int_job_postings') }}
),
dated as (
  select * from listings where listed_date is not null
),
jobicy_arbeitnow as (
  select l.job_key, 'jobicy_arbeitnow' as scope, l.listed_date
  from dated as l
  left anti join dated as m
    on m.job_key = l.job_key
    and m.source <> 'himalayas'
    and m.listed_date < l.listed_date
    and l.listed_date < m.live_until
  where l.source <> 'himalayas'
),
himalayas as (
  select l.job_key, 'himalayas' as scope, l.listed_date
  from dated as l
  left anti join dated as m
    on m.job_key = l.job_key
    and m.source = 'himalayas'
    and m.listed_date < l.listed_date
    and l.listed_date < m.live_until
  where l.source = 'himalayas'
),
all_boards as (
  select l.job_key, 'all_boards' as scope, l.listed_date
  from dated as l
  left anti join dated as m
    on m.job_key = l.job_key
    and m.listed_date < l.listed_date
    and l.listed_date < m.live_until
),
openings as (
  select * from jobicy_arbeitnow
  union all
  select * from himalayas
  union all
  select * from all_boards
)
select distinct job_key, scope, trunc(listed_date, 'WEEK') as week_start
from openings
