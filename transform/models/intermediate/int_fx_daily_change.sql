-- Change vs the previous published rate, not the previous calendar day (Monday vs Friday).
with rates as (
    select
        rate_date,
        pair,
        rate
    from {{ ref('stg_fx_rates') }}
),

with_prev as (
    select
        rate_date,
        pair,
        rate,
        lag(rate_date) over (partition by pair order by rate_date) as prev_rate_date,
        lag(rate) over (partition by pair order by rate_date) as prev_rate
    from rates
)

select
    rate_date,
    pair,
    rate,
    prev_rate_date,
    prev_rate,
    round(((rate / prev_rate - 1) * 100)::numeric, 2) as pct_change
from with_prev
