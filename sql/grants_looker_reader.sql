-- Hak akses read-only untuk Looker Studio (Tahap 11). Aman dijalankan ulang.
--
-- Jalankan di Neon SQL Editor: branch production, database jds, sebagai pemilik tabel (jds_owner).
--
-- PRASYARAT: role looker_reader dibuat lewat SQL, BUKAN lewat menu Roles di Neon Console.
-- Role dari Console otomatis menjadi anggota neon_superuser (bisa baca/tulis semua data).
-- Password tidak pernah ditulis di repo; buat sendiri lalu jalankan SEKALI di SQL Editor:
--
--     create role looker_reader with login password '<password-kuat-kamu>';
--
-- Cek setelahnya: uv run python -m jds.check_reader (dengan LOOKER_READER_URL di .env).

-- 1. Pastikan tidak ada hak di schema selain marts.
revoke all on schema raw, staging, ops from looker_reader;
revoke all on all tables in schema raw, staging, ops from looker_reader;
revoke create on schema public from looker_reader;

-- 2. Hanya boleh membaca schema marts.
grant usage on schema marts to looker_reader;
grant select on all tables in schema marts to looker_reader;

-- 3. dbt membuat ULANG tabel marts setiap run; grant pada tabel lama ikut hilang.
--    Default privileges membuat tabel baru milik jds_owner otomatis bisa dibaca.
alter default privileges for role jds_owner in schema marts
grant select on tables to looker_reader;

-- 4. Lapisan pengaman tambahan (yang utama tetap grant di atas).
alter role looker_reader set default_transaction_read_only = on;
alter role looker_reader set statement_timeout = '30s';
