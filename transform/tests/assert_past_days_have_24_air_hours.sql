-- Setiap hari yang SUDAH LEWAT (WIB) harus punya tepat 24 jam aktual dengan nilai PM2.5.
-- Hari ini dikecualikan karena sebagian jamnya masih prakiraan.
select date_wib, location_id, hours_actual, hours_with_pm25
from {{ ref('int_air_quality_daily') }}
where date_wib < (now() at time zone 'Asia/Jakarta')::date
  and (hours_actual <> 24 or hours_with_pm25 <> 24)
