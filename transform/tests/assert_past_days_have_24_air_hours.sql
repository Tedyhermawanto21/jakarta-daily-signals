-- Setiap hari SEBELUM hari aktual terakhir (per lokasi) harus punya 24 jam aktual dengan PM2.5.
-- Hari aktual terakhir = hari ingest terakhir; sebagian jamnya masih prakiraan -> dikecualikan.
-- Sengaja tidak memakai now(): is_forecast ditentukan relatif ke waktu ingest, jadi test ini juga.
-- Data basi (ingest berhenti) ditangkap oleh `dbt source freshness`, bukan oleh test ini.
with days as (
    select * from {{ ref('int_air_quality_daily') }}
),

latest as (
    select
        location_id,
        max(date_wib) as last_actual_date
    from days
    group by location_id
)

select
    d.date_wib,
    d.location_id,
    d.hours_actual,
    d.hours_with_pm25
from days as d
inner join latest as l
    on d.location_id = l.location_id
where
    d.date_wib < l.last_actual_date
    and (d.hours_actual <> 24 or d.hours_with_pm25 <> 24)
