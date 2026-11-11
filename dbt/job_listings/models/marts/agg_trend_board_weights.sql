-- One row per board (Phase 5, decision 14): its weight in the weekly trend, which is its share of all the boards' new
-- jobs over the trend's complete weeks (int_skill_weekly_by_board; a job on several boards counts on each). Recomputed
-- on every build, so every week of a build uses the same weights.
with board_weeks as (
  select distinct week_start, board, board_jobs
  from {{ ref('int_skill_weekly_by_board') }}
),
board_totals as (
  select board, sum(board_jobs) as jobs
  from board_weeks
  group by board
)
select board, jobs, jobs / sum(jobs) over () as weight
from board_totals
