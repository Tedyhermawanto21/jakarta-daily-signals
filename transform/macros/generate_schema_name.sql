{#-
  Default dbt menggabungkan schema target + custom (mis. "staging_marts").
  Proyek ini ingin nama schema persis seperti di dbt_project.yml: staging, marts.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
