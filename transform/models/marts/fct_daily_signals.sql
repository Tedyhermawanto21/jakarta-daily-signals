-- One row per (date_wib, location_id): FX rate, weather and air quality.
with days as (
    select * from {{ ref('stg_weather_daily') }}
),

fx as (
    select * from {{ ref('int_fx_daily_change') }}
    where pair = '{{ var("fx_pair") }}'
),

aq as (
    select * from {{ ref('int_air_quality_daily') }}
)

select
    d.date_wib,
    d.location_id,

    -- As-of join: latest rate on or before this date (weekends use Friday)
    fx.rate as usd_idr_rate,
    fx.rate_date as fx_rate_date,
    fx.prev_rate_date as fx_prev_rate_date,
    fx.pct_change as fx_pct_change,
    coalesce(fx.rate_date < d.date_wib, false) as fx_is_carried_forward,

    d.weather_code,
    d.temp_min_c,
    d.temp_max_c,
    d.temp_mean_c,
    d.precipitation_mm,
    d.wind_max_kmh,
    d.humidity_mean_pct,
    d.is_forecast as weather_is_forecast,

    aq.pm25_avg,
    aq.pm25_max,
    aq.pm25_peak_hour,
    coalesce(aq.hours_actual, 0) as aq_hours_actual,
    coalesce(aq.is_complete, false) as aq_is_complete,
    -- Indonesian ISPU category (PermenLHK P.14/2020), complete days only
    case
        when not coalesce(aq.is_complete, false) then null
        when aq.pm25_avg <= 15.5 then 'Baik'
        when aq.pm25_avg <= 55.4 then 'Sedang'
        when aq.pm25_avg <= 150.4 then 'Tidak Sehat'
        when aq.pm25_avg <= 250.4 then 'Sangat Tidak Sehat'
        else 'Berbahaya'
    end as pm25_category_ispu

from days as d
left join lateral (
    select r.*
    from fx as r
    where r.rate_date <= d.date_wib
    order by r.rate_date desc
    limit 1
) as fx on true
left join aq
    on
        d.date_wib = aq.date_wib
        and d.location_id = aq.location_id
