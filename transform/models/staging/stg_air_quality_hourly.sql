select
    ts_wib,
    date_wib,
    hour_wib::int as hour_wib,
    location_id,
    pm2_5 as pm25,
    pm10,
    us_aqi,
    is_forecast,
    grid_latitude,
    grid_longitude,
    to_timestamp(_dlt_load_id::numeric) as loaded_at
from {{ source('raw', 'air_quality_hourly') }}
