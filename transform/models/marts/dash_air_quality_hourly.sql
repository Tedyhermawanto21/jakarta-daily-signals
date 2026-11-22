-- Dashboard source for the hour-of-day PM2.5 pattern. Actual hours only.
select
    ts_wib,
    date_wib,
    hour_wib,
    lpad(hour_wib::text, 2, '0') || ':00' as hour_label,
    location_id,
    pm25,
    pm10,
    us_aqi
from {{ ref('stg_air_quality_hourly') }}
where not is_forecast
