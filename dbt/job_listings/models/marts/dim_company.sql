with job_postings as (
  select * from {{ ref("int_job_postings") }}
),
companies as (
  select
    company_key,
    max_by(company_name, published_at) as company_name,
    max_by(company_logo_url, published_at) filter (where company_logo_url is not null) as company_logo_url,
    min(published_at) as first_published_at,
    max(published_at) as last_published_at
  from job_postings
  group by company_key
)
select * from companies