# Column descriptions shared across layers

Each block is written once and used with `{{ doc('name') }}` in the staging, intermediate and mart YAML files, so a
column means the same thing wherever it appears. A model-specific note can follow the `doc()` call in the same
description. Silver's own columns are explained in more depth in `docs/silver-jobs-columns.md`.

## Keys

{% docs job_key %}
Surrogate key of the job: md5 hash of the company and title as int_job_postings matches them (lower-cased, letters and digits only, without a trailing legal form or gender tags). Postings of the same company and title are one job, on any board and in any location; so are a company's postings with the same description of at least 300 characters, which take the alphabetically first of their titles (Phase 5, decision 11).
{% enddocs %}

{% docs posting_key %}
Surrogate key of one posting: md5 hash of source and source_job_id. Several postings can be one job (job_key).
{% enddocs %}

{% docs company_key %}
Surrogate key of the company: md5 hash of the lower-cased, trimmed company name. Names differing only in case or surrounding spaces share one key, across sources.
{% enddocs %}

{% docs location_key %}
Surrogate key of the place: md5 hash of location_name, location_type and country_code.
{% enddocs %}

## Jobs

{% docs source %}
The API the job came from: jobicy, arbeitnow or himalayas.
{% enddocs %}

{% docs source_job_id %}
The job's ID at its source: Jobicy's id, Arbeitnow's slug or Himalayas' guid.
{% enddocs %}

{% docs url %}
Link to the posting: Jobicy's url, the Arbeitnow page, or Himalayas' applicationLink. Show it with every job listed: Jobicy asks for a link back, and Himalayas' terms require its application link for every Apply.
{% enddocs %}

{% docs title %}
Job title as posted. About 80 Himalayas titles still contain HTML entities such as &#x2f;.
{% enddocs %}

{% docs company_name %}
Company name as posted. About 15 Jobicy names still contain &amp;.
{% enddocs %}

{% docs company_logo_url %}
Company logo URL as posted. NULL for Arbeitnow, which sends no logos.
{% enddocs %}

{% docs published_at %}
When the job was published, in UTC. For Himalayas it's the job's last update, not its first publication.
{% enddocs %}

{% docs published_date %}
Day the job was published: the date of published_at, in UTC.
{% enddocs %}

{% docs published_month %}
First day of the month the job was published, in UTC. Matches month_start in dim_date.
{% enddocs %}

{% docs expires_at %}
When the job expires, in UTC. Only Himalayas gives one; NULL for Jobicy and Arbeitnow.
{% enddocs %}

{% docs is_remote %}
True for remote jobs. Always true for Jobicy and Himalayas, which list only remote jobs; Arbeitnow's own flag otherwise, so every on-site job is Arbeitnow's.
{% enddocs %}

{% docs is_listed_now %}
True while the job is open: it's in Jobicy's latest download, in either of Arbeitnow's last two downloads, or, for Himalayas, it expires after silver was built.
{% enddocs %}

{% docs seniority %}
Seniority from rules on the job title, else from the source's own level, else Unspecified. Scale: Intern < Junior < Mid < Senior < Lead < Director < Executive.
{% enddocs %}

{% docs seniority_source %}
Where seniority came from: title, source_level or none.
{% enddocs %}

{% docs first_seen_at %}
When a downloaded file containing the job was first landed.
{% enddocs %}

{% docs last_seen_at %}
When a downloaded file containing the job was last landed.
{% enddocs %}

{% docs times_seen %}
Number of downloads (ingestion runs) that contained the job; at least 1.
{% enddocs %}

{% docs built_at %}
When silver was built. The same for every row; source freshness checks use it.
{% enddocs %}

## Salaries

{% docs salary_min %}
Minimum salary as posted, in salary_currency per salary_period. NULL when not given, and always for Arbeitnow, which publishes no salaries.
{% enddocs %}

{% docs salary_max %}
Maximum salary as posted, in salary_currency per salary_period. NULL when not given, and always for Arbeitnow.
{% enddocs %}

{% docs salary_currency %}
Currency of the posted salary, e.g. USD or EUR.
{% enddocs %}

{% docs salary_period %}
Period of the posted salary: yearly or annual, monthly, fortnightly, weekly, daily or hourly. A missing period counts as yearly.
{% enddocs %}

{% docs salary_min_usd_yearly %}
Minimum salary in yearly USD: amount x yearly factor (monthly 12, weekly 52, daily 260, hourly 2,080...) x the latest ECB rate on or before published_date. NULL for an unknown period or a currency without a rate. Not checked for plausibility.
{% enddocs %}

{% docs salary_max_usd_yearly %}
Maximum salary in yearly USD, converted like salary_min_usd_yearly. Not checked for plausibility.
{% enddocs %}

{% docs salary_mid_usd_yearly %}
Midpoint of the yearly USD salary range. A range with only one bound uses that bound. NULL when the job has no yearly USD salary.
{% enddocs %}

{% docs salary_is_plausible %}
True when both yearly USD bounds are between 5,000 and 1,500,000 and the minimum doesn't exceed the maximum; a missing bound is replaced by the other. NULL when the job has no yearly USD salary. Salary charts use plausible salaries only.
{% enddocs %}

## Skills

{% docs skill %}
Skill name as written in the skill taxonomy (skills.csv).
{% enddocs %}

{% docs category %}
Taxonomy category, e.g. Programming Languages or CRM & Sales Tools.
{% enddocs %}

{% docs taxonomy_version %}
12-character fingerprint of the skill list's content. Changes whenever skills.csv changes.
{% enddocs %}

{% docs mentions %}
How many times the skill is mentioned in the job's title and in the description's lines about the job (not the employer's own text); at least 1.
{% enddocs %}

{% docs in_title %}
True when the skill appears in the job title.
{% enddocs %}

## Places, industries and job types

{% docs location_raw %}
One place as the source listed it, e.g. USA or Bristol. Empty when the job's location was empty.
{% enddocs %}

{% docs location_name %}
The place's name: a city, country or region, Anywhere for Worldwide, or the cleaned text of an unknown place. NULL for an empty location.
{% enddocs %}

{% docs location_type %}
city, country, region, worldwide or unknown.
{% enddocs %}

{% docs country_code %}
Two-letter ISO country code, shared by a country and its cities; use it for map charts. NULL for regions, Worldwide and unknown places.
{% enddocs %}

{% docs location_region %}
Region of the place: North America, LATAM, Europe, Middle East & Africa, APAC or Antarctica for cities and countries; the region itself for region-level places (e.g. EMEA); Worldwide for Anywhere. NULL for unknown places.
{% enddocs %}

{% docs country_name %}
Country name in English.
{% enddocs %}

{% docs country_region %}
Region the country belongs to: North America, LATAM, Europe, Middle East & Africa, APAC or Antarctica (5 remote territories).
{% enddocs %}

{% docs industry %}
Industry, mapped from each source's own categories to one shared list (industries.csv).
{% enddocs %}

{% docs job_type %}
Full-Time, Part-Time, Contract, Internship or Temporary, mapped from each source's own values (job_types.csv).
{% enddocs %}
