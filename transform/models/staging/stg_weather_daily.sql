select
    date_wib,
    location_id,
    weather_code::int as weather_code,
    temperature_2m_min as temp_min_c,
    temperature_2m_max as temp_max_c,
    temperature_2m_mean as temp_mean_c,
    precipitation_sum as precipitation_mm,
    rain_sum as rain_mm,
    precipitation_hours,
    wind_speed_10m_max as wind_max_kmh,
    relative_humidity_2m_mean as humidity_mean_pct,
    is_forecast,
    grid_latitude,
    grid_longitude,
    to_timestamp(_dlt_load_id::numeric) as loaded_at
from {{ source('raw', 'weather_daily') }}
