{#-
  Default dbt menggabungkan schema target + custom (mis. "staging_marts").
  Proyek ini ingin nama schema persis seperti di dbt_project.yml: staging, marts.

  CI (Tahap 10): env DBT_SCHEMA_PREFIX=ci_pr_<n> -> ci_pr_<n>_staging, ci_pr_<n>_marts,
  supaya setiap PR punya schema sendiri dan tidak menimpa staging/marts.
  Prefix divalidasi di jds.run_dbt; source `raw` tidak terpengaruh (dibaca apa adanya).
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set base = target.schema if custom_schema_name is none else custom_schema_name | trim -%}
    {%- set prefix = env_var('DBT_SCHEMA_PREFIX', '') | trim -%}
    {%- if prefix -%}
        {{ prefix }}_{{ base }}
    {%- else -%}
        {{ base }}
    {%- endif -%}
{%- endmacro %}
