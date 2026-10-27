with days as (
  {{ dbt_utils.date_spine(
      datepart="day",
      start_date="date'2026-10-01'",
      end_date="date_add(current_date(), 1)"
  ) }}
),
dates as (
  select cast(date_day as date) as date_day
  from days
)
select
  date_day,
  year(date_day) as year,
  quarter(date_day) as quarter,
  month(date_day) as month,
  date_format(date_day, 'MMMM') as month_name,
  trunc(date_day, 'MM') as month_start,
  trunc(date_day, 'WEEK') as week_start,
  weekday(date_day) + 1 as day_of_week,
  date_format(date_day, 'EEEE') as day_name,
  weekday(date_day) >= 5 as is_weekend
from dates