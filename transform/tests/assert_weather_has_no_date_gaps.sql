-- Fails when a date is missing between weather dates (per location).
select
    location_id,
    date_wib,
    next_date
from (
    select
        location_id,
        date_wib,
        lead(date_wib) over (partition by location_id order by date_wib) as next_date
    from {{ ref('stg_weather_daily') }}
) as t
where next_date - date_wib > 1
