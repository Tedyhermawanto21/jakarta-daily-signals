-- Dashboard source: one row per actual day and location, anomaly flags from fct_anomalies.
with signals as (
    select * from {{ ref('fct_daily_signals') }}
    where not weather_is_forecast
),

anomalies as (
    select * from {{ ref('fct_anomalies') }}
)

select
    s.date_wib,
    s.location_id,

    s.usd_idr_rate,
    s.fx_rate_date,
    s.fx_is_carried_forward,
    -- Null on carried-forward days so a Friday move is not counted three times.
    case when not s.fx_is_carried_forward then s.fx_pct_change end as fx_pct_change_day,
    case when fx.signal_date is not null then 1 else 0 end as fx_anomaly_flag,

    s.temp_min_c,
    s.temp_max_c,
    s.temp_mean_c,
    s.precipitation_mm,
    s.wind_max_kmh,
    s.humidity_mean_pct,

    s.aq_is_complete,
    s.pm25_avg,
    s.pm25_max,
    s.pm25_peak_hour,
    s.pm25_category_ispu,
    case when pm.signal_date is not null then 1 else 0 end as pm25_anomaly_flag,
    {{ var('pm25_threshold') }}::numeric as pm25_threshold

from signals as s
left join anomalies as fx
    on
        fx.alert_type = 'fx_move'
        and s.fx_rate_date = fx.signal_date
        and not s.fx_is_carried_forward
left join anomalies as pm
    on
        pm.alert_type = 'pm25_high'
        and s.date_wib = pm.signal_date
        and s.location_id = pm.location_id
