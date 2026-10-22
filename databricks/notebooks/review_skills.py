# Databricks notebook source
# MAGIC %md
# MAGIC # Review: skill matches, seniority and locations (not part of the Job)
# MAGIC
# MAGIC A tool for checking silver by hand. Run it from the workspace when `skills.csv` or the mappings change; it only
# MAGIC reads tables, and it matches with the `skills.csv` uploaded by the last `databricks bundle deploy`.
# MAGIC
# MAGIC 1. **Sample:** about `sample_size` jobs **per source**, spread over each source's industries in proportion to their
# MAGIC    size (at least one per industry; jobs without an industry form their own group). The same `seed` picks the
# MAGIC    same jobs, so runs before and after a change compare the same postings.
# MAGIC 2. **Matches:** every counted match in the sample with the text around it, to mark right or wrong. Jobs without
# MAGIC    any match are listed too, since that's where missed skills show up.
# MAGIC 3. **Seniority:** each sampled job's title, the source's own level values, and the seniority silver derived.
# MAGIC 4. **Locations:** each sampled job's raw location values and where they were placed.
# MAGIC 5. **Candidate terms:** capitalised words that many companies' postings use but no skill alias covers.
# MAGIC
# MAGIC Parameters: `catalog`, `bundle_root` (empty: the repo root two folders above this notebook), `seed`,
# MAGIC `sample_size` and `sources` (comma-separated, e.g. `arbeitnow,himalayas`; empty for all).

# COMMAND ----------

import os
import sys

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bundle_root", "")
dbutils.widgets.text("seed", "2026-10-19")
dbutils.widgets.text("sample_size", "50")
dbutils.widgets.text("sources", "")

catalog = dbutils.widgets.get("catalog")
bundle_root = dbutils.widgets.get("bundle_root") or os.path.abspath("../..")
seed = dbutils.widgets.get("seed")
sample_size = int(dbutils.widgets.get("sample_size"))
sources = [source.strip() for source in dbutils.widgets.get("sources").split(",") if source.strip()]
# A SQL condition that keeps the chosen sources (or every source when none is given).
source_filter = "j.source IN (" + ", ".join(f"'{source}'" for source in sources) + ")" if sources else "true"

# The bundle uploads the repo's transform/ package next to databricks/; make it importable.
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

from transform.skills import SkillMatcher

matcher = SkillMatcher.from_csv(f"{bundle_root}/databricks/reference/skills.csv")
print(f"Skill list version {matcher.taxonomy_version}, seed {seed!r}, sample size about {sample_size}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Sample

# COMMAND ----------

sample = spark.sql(f"""
    WITH jobs_by_industry AS (
        SELECT j.source, j.source_job_id, j.title, j.company_name, j.description_text,
            coalesce(min(i.industry), '(no industry)') AS industry
        FROM {catalog}.silver.jobs AS j
        LEFT JOIN {catalog}.silver.job_industries AS i
            ON i.source = j.source AND i.source_job_id = j.source_job_id
        WHERE {source_filter}
        GROUP BY ALL
    ),
    ranked AS (
        SELECT *,
            row_number() OVER (
                PARTITION BY source, industry ORDER BY xxhash64('{seed}', source, source_job_id)
            ) AS pick,
            count(*) OVER (PARTITION BY source, industry) AS industry_jobs,
            count(*) OVER (PARTITION BY source) AS source_jobs
        FROM jobs_by_industry
    )
    SELECT source, source_job_id, industry, title, company_name, description_text
    FROM ranked
    WHERE pick <= greatest(1, round({sample_size} * industry_jobs / source_jobs))
    ORDER BY source, industry, pick
""").collect()

for source in sorted({job["source"] for job in sample}):
    picked = [job for job in sample if job["source"] == source]
    print(f"{source}: {len(picked)} jobs sampled from {len({job['industry'] for job in picked})} industries")

# The sampled jobs as a temp view, for the seniority and location sections.
spark.createDataFrame(
    [(job["source"], job["source_job_id"]) for job in sample], "source STRING, source_job_id STRING"
).createOrReplaceTempView("sampled_jobs")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Matches

# COMMAND ----------

matches = []
for job in sample:
    found = matcher.snippets(job["title"], job["description_text"], job["company_name"])
    for match in found:
        matches.append(
            (job["source"], job["industry"], job["source_job_id"], job["title"],
             match["skill"], match["field"], match["snippet"])
        )
    if not found:
        matches.append(
            (job["source"], job["industry"], job["source_job_id"], job["title"], None, None, "(no skills found)")
        )

print(f"{sum(match[4] is not None for match in matches)} matches in {len(sample)} jobs")
display(
    spark.createDataFrame(
        matches,
        "source STRING, industry STRING, source_job_id STRING, title STRING, skill STRING, field STRING, snippet STRING",
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Seniority
# MAGIC
# MAGIC `seniority_source` says where the level came from: `title` (a rule in `transform/seniority.py`), `source_level`
# MAGIC (the highest of `source_levels`, mapped through `levels.csv`) or `none` (Unspecified).

# COMMAND ----------

display(spark.sql(f"""
    SELECT j.source, j.title, j.source_levels, j.seniority, j.seniority_source
    FROM {catalog}.silver.jobs AS j
    JOIN sampled_jobs AS s ON s.source = j.source AND s.source_job_id = j.source_job_id
    ORDER BY j.source, j.seniority_source, j.title
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Locations

# COMMAND ----------

display(spark.sql(f"""
    SELECT l.source, j.title, l.location_raw, l.location_name, l.location_type, l.country_code, l.region
    FROM {catalog}.silver.job_locations AS l
    JOIN sampled_jobs AS s ON s.source = l.source AND s.source_job_id = l.source_job_id
    JOIN {catalog}.silver.jobs AS j ON j.source = l.source AND j.source_job_id = l.source_job_id
    ORDER BY l.source, l.location_type, l.location_raw
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Candidate terms
# MAGIC
# MAGIC A capitalised word (or product-style name such as `Next.js`) becomes a candidate when postings from at least
# MAGIC `MIN_COMPANIES` companies use it, it's rarely written in lowercase (which filters out ordinary words at the
# MAGIC start of a sentence), and no skill alias matches it yet. Counting companies rather than jobs keeps one employer's
# MAGIC own name, repeated across its postings, from looking popular.

# COMMAND ----------

import re
from collections import Counter, defaultdict

MIN_COMPANIES = 5
TERM = re.compile(r"(?<![\w.+#-])[A-Z][A-Za-z0-9.+#-]*[A-Za-z0-9+#]")
LOWER_WORD = re.compile(r"(?<![\w.+#-])[a-z][a-z0-9.+#-]*[a-z0-9+#]")

companies = defaultdict(set)  # term -> companies whose postings use it
jobs_capitalised = Counter()  # term -> jobs using it capitalised
jobs_lowercase = Counter()  # lowercase word -> jobs using it in lowercase
for job in spark.table(f"{catalog}.silver.jobs").select("company_name", "title", "description_text").collect():
    text = f"{job['title']}\n{job['description_text'] or ''}"
    terms = set(TERM.findall(text))
    for term in terms:
        companies[term].add(job["company_name"])
    jobs_capitalised.update(terms)
    jobs_lowercase.update(set(LOWER_WORD.findall(text)))

candidates = [
    (term, len(companies[term]), jobs_capitalised[term], jobs_lowercase[term.lower()])
    for term in companies
    if len(companies[term]) >= MIN_COMPANIES
    and jobs_lowercase[term.lower()] < 0.25 * jobs_capitalised[term]
    and not matcher.match(None, term)
]
candidates.sort(key=lambda candidate: (-candidate[1], candidate[0]))

print(f"{len(candidates)} candidate terms")
display(spark.createDataFrame(candidates[:150], "term STRING, companies INT, jobs INT, jobs_lowercase INT"))
