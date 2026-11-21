{#- Format angka & tanggal gaya Indonesia di SQL, sama dengan jds.alerts.rules. -#}

{#- 18263.5 -> '18.263,5' (pola to_char memakai ',' ribuan dan '.' desimal, lalu ditukar) -#}
{% macro fmt_num_id(expr, pattern='FM999,999,990.0') -%}
    translate(to_char({{ expr }}, '{{ pattern }}'), ',.', '.,')
{%- endmacro %}

{#- 2026-11-17 -> '17 Nov' -#}
{% macro fmt_short_date_id(expr) -%}
    extract(day from {{ expr }})::int || ' '
    || (array['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'])[extract(month from {{ expr }})::int]
{%- endmacro %}
