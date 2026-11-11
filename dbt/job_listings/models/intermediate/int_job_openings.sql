-- One row per job x scope x week in which an opening of the job began (Phase 5, decisions 12 to 14). Each posting is a
-- listing: Jobicy and Arbeitnow on its publish date, Himalayas on the day it was first seen. A listing starts a new
-- opening when none of the job's earlier listings is still live, so a repost while one is live is the same opening and a
-- later one is a new opening. A Jobicy or Arbeitnow listing counts as live for 8 weeks (their feeds show only 7 days, so
-- we can't see when a job closes); a Himalayas one until it expires, a median of 59 days, which is also when the
-- Himalayas history counts a job again. Each scope looks only at its own listings:
--   jobicy, arbeitnow, himalayas: one board's, for each board's own share in the weekly trend (decision 14);
--   jobicy_arbeitnow: those two boards', and all_boards: every listing, for the overlap history, which keeps the trend's
--   job counts at one per opening across the boards (decisions 12 and 13).
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
per_board as (
  select l.job_key, l.source as scope, l.listed_date
  from dated as l
  left anti join dated as m
    on m.job_key = l.job_key
    and m.source = l.source
    and m.listed_date < l.listed_date
    and l.listed_date < m.live_until
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
all_boards as (
  select l.job_key, 'all_boards' as scope, l.listed_date
  from dated as l
  left anti join dated as m
    on m.job_key = l.job_key
    and m.listed_date < l.listed_date
    and l.listed_date < m.live_until
),
openings as (
  select * from per_board
  union all
  select * from jobicy_arbeitnow
  union all
  select * from all_boards
)
select distinct job_key, scope, trunc(listed_date, 'WEEK') as week_start
from openings
