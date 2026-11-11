-- The weekly trend's board weights (Phase 5, decision 14) must add up to 1, or every share would be scaled. Returns a row,
-- which fails the test, when they don't.
select sum(weight) as total_weight
from {{ ref('agg_trend_board_weights') }}
having abs(sum(weight) - 1) > 1e-9
