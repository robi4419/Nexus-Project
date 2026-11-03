with source as (
  select * from {{ source('silver', 'jobs') }}
),
renamed as (
  select
    {{ dbt_utils.generate_surrogate_key(['source', 'source_job_id']) }} as posting_key,
    source, source_job_id, url, title, company_name, company_logo_url,
    published_at, published_date, expires_at, is_remote, is_listed_now,
    seniority, seniority_source,
    salary_min, salary_max, salary_currency, salary_period, salary_min_usd_yearly, salary_max_usd_yearly,
    first_seen_at, last_seen_at, times_seen, built_at,
    -- a fingerprint of a description long enough to tell roles apart, for finding one job posted several times
    case when length(description_text) >= 300
      then md5(lower(regexp_replace(description_text, '\\s+', ' ')))
    end as description_hash
  from source
)
select * from renamed
