-- Every day before the last actual day must have 24 actual hours with PM2.5.
-- Not based on now(): stale data is caught by `dbt source freshness` instead.
with days as (
    select * from {{ ref('int_air_quality_daily') }}
),

latest as (
    select
        location_id,
        max(date_wib) as last_actual_date
    from days
    group by location_id
)

select
    d.date_wib,
    d.location_id,
    d.hours_actual,
    d.hours_with_pm25
from days as d
inner join latest as l
    on d.location_id = l.location_id
where
    d.date_wib < l.last_actual_date
    and (d.hours_actual <> 24 or d.hours_with_pm25 <> 24)
