-- One row per posting: the industry its job shows when this posting speaks for the job (Phase 5, decision 15).
-- fct_job_postings picks that posting, the same one that gives the job its title.
with postings as (
  select posting_key, job_key from {{ ref('int_job_postings') }}
),
predictions as (
  select * from {{ ref('stg_silver__job_industry_predictions') }}
),
labels as (
  select job_key, industry from {{ ref('stg_silver__industry_labels') }}
),
industry_list as (
  select industry from {{ ref('stg_silver__ref_industry_list') }}
),
answers as (
  select
    p.posting_key, p.job_key,
    l.industry as hand_label,
    m.industry as model_industry,
    coalesce(m.industry_probability >= {{ var('industry_sure') }}, false) as is_sure_of_industry,
    -- only groups of several industries have a "<Group>, unspecified" row in the list
    u.industry as group_only,
    coalesce(m.group_probability >= {{ var('industry_sure') }}, false) as is_sure_of_group
  from postings as p
  left join predictions as m
    on m.posting_key = p.posting_key
  left join labels as l
    on l.job_key = p.job_key
  left join industry_list as u
    on u.industry = concat(m.industry_group, ', unspecified')
)
select
  posting_key, job_key,
  case
    when hand_label is not null then hand_label
    when is_sure_of_industry then model_industry
    when is_sure_of_group and group_only is not null then group_only
    else 'Not classified'
  end as industry,
  case
    when hand_label is not null then 'hand label'
    when is_sure_of_industry then 'model'
    when is_sure_of_group and group_only is not null then 'model, group only'
    else 'not classified'
  end as industry_source
from answers
