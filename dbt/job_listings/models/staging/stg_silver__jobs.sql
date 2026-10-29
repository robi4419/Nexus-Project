with source as (
  select * from {{ source('silver', 'jobs') }}
),
renamed as (
  select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as job_key,
    source, source_job_id, url, title, company_name, company_logo_url,
    published_at, published_date, expires_at, is_remote, is_listed_now,
    seniority, seniority_source,
    salary_min, salary_max, salary_currency, salary_period, salary_min_usd_yearly, salary_max_usd_yearly,
    first_seen_at, last_seen_at, times_seen, built_at
  from source
)
select * from renamed