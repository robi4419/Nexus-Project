with jobs as (
  select * from {{ ref("stg_silver__jobs") }}
),
final as (
  select
    *,
    {{ dbt_utils.generate_surrogate_key(['lower(trim(company_name))']) }} as company_key,
    trunc(published_date, 'MM') as published_month,
    (coalesce(salary_min_usd_yearly, salary_max_usd_yearly) +
    coalesce(salary_max_usd_yearly, salary_min_usd_yearly)) / 2 as salary_mid_usd_yearly,
    case 
      when coalesce(salary_min_usd_yearly, salary_max_usd_yearly) is null then null
      else (coalesce(salary_min_usd_yearly, salary_max_usd_yearly) between 5000 and 1500000)
        and (coalesce(salary_max_usd_yearly, salary_min_usd_yearly) between 5000 and 1500000)
        and (coalesce(salary_min_usd_yearly, salary_max_usd_yearly) <= coalesce(salary_max_usd_yearly, salary_min_usd_yearly))
    end as salary_is_plausible
  from jobs
)
select * from final