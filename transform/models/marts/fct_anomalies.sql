-- 1 baris per anomali (signal_date, alert_type, location_id). Dibaca oleh alert Telegram (Tahap 8).
-- Kurs tidak terikat lokasi -> location_id = 'all'.
with fx as (
    select * from {{ ref('int_fx_daily_change') }}
    where pair = '{{ var("fx_pair") }}'
),

signals as (
    select * from {{ ref('fct_daily_signals') }}
)

select
    rate_date as signal_date,
    'all' as location_id,
    'fx_move' as alert_type,
    pct_change as value,
    {{ var('fx_change_threshold_pct') }}::numeric as threshold,
    format(
        'USD/IDR %s (%s%% vs %s)',
        {{ fmt_num_id('rate', 'FM999,999,990') }},
        {{ fmt_num_id('pct_change', 'FMS990.00') }},
        {{ fmt_short_date_id('prev_rate_date') }}
    ) as detail
from fx
where abs(pct_change) > {{ var('fx_change_threshold_pct') }}

union all

select
    date_wib as signal_date,
    location_id,
    'pm25_high' as alert_type,
    pm25_avg as value,
    {{ var('pm25_threshold') }}::numeric as threshold,
    format(
        'PM2.5 rata-rata %s µg/m³ (%s), puncak %s µg/m³ jam %s:00 WIB',
        {{ fmt_num_id('pm25_avg') }},
        pm25_category_ispu,
        {{ fmt_num_id('pm25_max') }},
        lpad(pm25_peak_hour::text, 2, '0')
    ) as detail
from signals
where aq_is_complete
    and pm25_avg > {{ var('pm25_threshold') }}
