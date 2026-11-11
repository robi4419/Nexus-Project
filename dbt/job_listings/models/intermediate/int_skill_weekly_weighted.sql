-- One row per complete week x skill (Phase 5, decision 14): the share of new jobs asking for the skill, with each board's
-- own share combined by fixed weights (agg_trend_board_weights), so a board posting more or fewer jobs in a week doesn't
-- move the line.
--   share: sum(w * p) / sum(w) over the boards with new jobs that week, p being a board's own share. A board with none
--     is left out of that week, and the other boards' weights scale up to 1.
--   share_change: the same over the boards with new jobs in both weeks, of each board's change in p. It's share minus
--     the previous week's share, except in a week a board is missing, which then doesn't count as a change.
--   chance_low, chance_high: where the share would land by chance, at 95%, if no board's own share had changed since
--     the week before: (share - share_change) +/- 1.96 * sqrt(sum(w^2 * q * (1 - q) * (1/n + 1/n_prev))) / sum(w), over
--     the boards in both weeks, with n a board's new jobs per week and q its share over the two weeks together.
-- Fractions are rounded to 6 decimals (a ten-thousandth of a percentage point). The first week has no change or band.
with by_board as (
  select
    b.week_start,
    b.skill,
    b.board,
    b.skill_jobs,
    b.board_jobs,
    w.weight,
    b.skill_jobs / b.board_jobs as board_share
  from {{ ref('int_skill_weekly_by_board') }} as b
  join {{ ref('agg_trend_board_weights') }} as w
    on w.board = b.board
  where b.board_jobs > 0
),
paired as (
  select
    cur.week_start,
    cur.skill,
    cur.weight,
    cur.board_share,
    cur.board_jobs,
    prev.board_share as prev_board_share,
    prev.board_jobs as prev_board_jobs,
    (cur.skill_jobs + prev.skill_jobs) / (cur.board_jobs + prev.board_jobs) as pooled_share
  from by_board as cur
  left join by_board as prev
    on prev.board = cur.board
    and prev.skill = cur.skill
    and prev.week_start = date_sub(cur.week_start, 7)
),
weekly as (
  select
    week_start,
    skill,
    sum(weight * board_share) / sum(weight) as share,
    sum(case when prev_board_share is not null then weight end) as paired_weight,
    sum(case when prev_board_share is not null then weight * (board_share - prev_board_share) end) as paired_change,
    sum(
      case when prev_board_share is not null
        then weight * weight * pooled_share * (1 - pooled_share) * (1 / board_jobs + 1 / prev_board_jobs)
      end
    ) as paired_variance
  from paired
  group by week_start, skill
),
changed as (
  select
    week_start,
    skill,
    share,
    lag(share) over (partition by skill order by week_start) as prev_share,
    paired_change / paired_weight as share_change,
    1.96 * sqrt(paired_variance) / paired_weight as margin
  from weekly
)
select
  week_start,
  skill,
  round(share, 6) as share,
  round(prev_share, 6) as prev_share,
  round(share_change, 6) as share_change,
  -- greatest() skips NULLs, so the first week needs the case to stay NULL
  case when share_change is not null then round(greatest(share - share_change - margin, 0), 6) end as chance_low,
  round(share - share_change + margin, 6) as chance_high
from changed
