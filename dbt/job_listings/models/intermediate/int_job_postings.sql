with postings as (
  select * from {{ ref("stg_silver__jobs") }}
),
-- Matching keys: lower-cased, letters and digits only; a trailing legal form comes off the company ("Acme, Inc."),
-- gender tags come off the title ("(m/w/d)", "(all genders)").
matching as (
  select
    *,
    regexp_replace(
      regexp_replace(
        lower(trim(company_name)),
        '[\\s,]+(inc|llc|ltd|limited|gmbh|ag|sa|sas|bv|b\\.v|plc|corp|corporation|co|company|group|se)\\.?$', ''
      ),
      '[^\\p{L}\\p{N}]+', ''
    ) as company_match,
    regexp_replace(
      regexp_replace(
        lower(title),
        '\\(\\s*(?:[mwfdx]\\s*[/|,]\\s*)+[mwfdx]\\s*\\)|\\(gn\\)|\\(all genders\\)', ''
      ),
      '[^\\p{L}\\p{N}]+', ''
    ) as title_match
  from postings
),
-- One job per company and title (Phase 5, decision 11). A description long enough to tell roles apart, shared by several
-- titles of a company (one role posted per country, "... - Brazil"), joins those titles: the job takes the
-- alphabetically first one. Two rounds of title -> description -> title also join titles linked through a second
-- description.
round_1 as (
  select *,
    case when description_hash is null then title_match
      else min(title_match) over (partition by company_match, description_hash)
    end as label_1
  from matching
),
round_2 as (
  select *, min(label_1) over (partition by company_match, title_match) as label_2
  from round_1
),
round_3 as (
  select *,
    case when description_hash is null then label_2
      else min(label_2) over (partition by company_match, description_hash)
    end as label_3
  from round_2
),
round_4 as (
  select *, min(label_3) over (partition by company_match, title_match) as job_title_match
  from round_3
),
final as (
  select
    * except (company_match, title_match, label_1, label_2, label_3, job_title_match),
    {{ dbt_utils.generate_surrogate_key(['company_match', 'job_title_match']) }} as job_key,
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
  from round_4
)
select * from final
