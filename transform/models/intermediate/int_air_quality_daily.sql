-- Ringkasan harian PM2.5 dari JAM AKTUAL saja (prakiraan tidak dihitung sebagai fakta).
-- is_complete = 24 jam aktual dengan nilai PM2.5; hanya hari lengkap yang boleh dinilai anomali.
with actual as (
    select date_wib, location_id, hour_wib, pm25
    from {{ ref('stg_air_quality_hourly') }}
    where not is_forecast
)

select
    date_wib,
    location_id,
    count(*) as hours_actual,
    count(pm25) as hours_with_pm25,
    round(avg(pm25)::numeric, 1) as pm25_avg,
    round(max(pm25)::numeric, 1) as pm25_max,
    -- jam dengan PM2.5 tertinggi; jika seri, ambil jam paling awal
    (array_agg(hour_wib order by pm25 desc nulls last, hour_wib))[1] as pm25_peak_hour,
    count(pm25) = 24 as is_complete
from actual
group by date_wib, location_id
