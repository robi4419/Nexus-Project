{#
  Post-hook of fct_job_postings (Phase 5, decision 15): deletes the hand labels whose job is no longer in gold.
  Only Himalayas jobs leave gold, at expiry, and their labels must go with them.

  It deletes nothing when more than industry_labels_max_purge_share of the labels would go in one build: that isn't
  expiry but a broken build, or a changed job_key rule, which would otherwise delete every label.
  tests/assert_industry_labels_follow_gold.sql then warns with the number of rows left waiting.
#}
{% macro purge_industry_labels() %}
merge into {{ source('silver', 'industry_labels') }} as labels
using (
  select job_key
  from (
    select
      l.job_key,
      f.job_key is null as job_is_gone,
      count_if(f.job_key is null) over () as labels_gone,
      count(*) over () as labels_all
    from {{ source('silver', 'industry_labels') }} as l
    left join {{ this }} as f
      on f.job_key = l.job_key
  )
  where job_is_gone
    and labels_gone <= {{ var('industry_labels_max_purge_share') }} * labels_all
) as gone
on labels.job_key = gone.job_key
when matched then delete
{% endmacro %}
