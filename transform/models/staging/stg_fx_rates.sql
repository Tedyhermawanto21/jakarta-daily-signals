select
    rate_date,
    base,
    quote,
    base || '/' || quote as pair,
    rate,
    source as rate_source,
    to_timestamp(_dlt_load_id::numeric) as loaded_at
from {{ source('raw', 'fx_rates') }}
