-- Dashboard scorecards: one row per location for the last actual day, like the Telegram
-- summary. Labels stay Indonesian because the dashboard is.
with daily as (
    select * from {{ ref('dash_daily_signals') }}
),

latest as (
    select
        location_id,
        max(date_wib) as summary_date
    from daily
    group by location_id
),

forecast as (
    select * from {{ ref('fct_daily_signals') }}
    where weather_is_forecast
),

anomalies as (
    select * from {{ ref('fct_anomalies') }}
),

status as (
    select
        l.location_id,
        count(a.alert_type) as anomaly_count,
        string_agg(
            case a.alert_type
                when 'pm25_high' then 'Udara tidak sehat'
                when 'fx_move' then 'Kurs bergerak tajam'
            end,
            ', ' order by a.alert_type
        ) as anomaly_titles
    from latest as l
    inner join daily as d
        on
            l.location_id = d.location_id
            and l.summary_date = d.date_wib
    left join anomalies as a
        on
            (
                a.alert_type = 'pm25_high'
                and d.date_wib = a.signal_date
                and d.location_id = a.location_id
            )
            or (a.alert_type = 'fx_move' and d.fx_rate_date = a.signal_date)
    group by l.location_id
)

select
    d.location_id,
    d.date_wib as summary_date,
    d.usd_idr_rate,
    d.fx_rate_date,
    fx.pct_change as fx_pct_change,
    d.temp_min_c,
    d.temp_max_c,
    d.precipitation_mm,
    d.wind_max_kmh,
    d.pm25_avg,
    d.pm25_max,
    d.pm25_peak_hour,
    d.pm25_category_ispu,
    st.anomaly_count,
    case
        when st.anomaly_count > 0 then 'Ada anomali: ' || st.anomaly_titles
        else 'Tidak ada anomali'
    end as status_text,
    f.date_wib as forecast_date,
    f.temp_min_c as forecast_temp_min_c,
    f.temp_max_c as forecast_temp_max_c,
    f.precipitation_mm as forecast_precipitation_mm,
    (now() at time zone 'Asia/Jakarta') as built_at_wib
from latest as l
inner join daily as d
    on
        l.location_id = d.location_id
        and l.summary_date = d.date_wib
inner join status as st
    on l.location_id = st.location_id
left join {{ ref('int_fx_daily_change') }} as fx
    on
        d.fx_rate_date = fx.rate_date
        and fx.pair = '{{ var("fx_pair") }}'
left join forecast as f
    on
        l.location_id = f.location_id
        and f.date_wib = l.summary_date + 1
