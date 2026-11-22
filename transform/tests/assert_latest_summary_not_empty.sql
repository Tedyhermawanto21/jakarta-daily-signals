-- Every location must have a summary row, otherwise the dashboard scorecards are empty.
select l.location_id
from (select distinct location_id from {{ ref('dash_daily_signals') }}) as l
left join {{ ref('dash_latest_summary') }} as s
    on l.location_id = s.location_id
where s.location_id is null
