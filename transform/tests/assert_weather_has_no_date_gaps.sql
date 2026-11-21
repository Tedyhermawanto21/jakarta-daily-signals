-- Gagal jika ada tanggal yang bolong di antara tanggal cuaca (per lokasi).
-- Backfill Tahap 6 pernah menghasilkan baris kosong; tanggal hilang adalah bentuk lain dari masalah yang sama.
select location_id, date_wib, next_date
from (
    select
        location_id,
        date_wib,
        lead(date_wib) over (partition by location_id order by date_wib) as next_date
    from {{ ref('stg_weather_daily') }}
) as t
where next_date - date_wib > 1
