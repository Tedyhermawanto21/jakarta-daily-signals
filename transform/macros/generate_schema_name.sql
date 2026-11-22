{#-
  Use custom schema names as-is (staging, marts) instead of dbt's "<target>_<custom>".
  In CI, DBT_SCHEMA_PREFIX=ci_pr_<n> gives every PR its own ci_pr_<n>_* schemas.
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
