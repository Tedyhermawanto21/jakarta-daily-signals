-- Daily PM2.5 from actual hours only; only complete days (24 hours) are judged for anomalies.
with actual as (
    select
        date_wib,
        location_id,
        hour_wib,
        pm25
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
    -- ties go to the earliest hour
    (array_agg(hour_wib order by pm25 desc nulls last, hour_wib asc))[1] as pm25_peak_hour,
    count(pm25) = 24 as is_complete
from actual
group by date_wib, location_id
