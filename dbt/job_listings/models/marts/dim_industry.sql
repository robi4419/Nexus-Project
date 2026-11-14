select industry, industry_group, sort_order
from {{ ref('stg_silver__ref_industry_list') }}
