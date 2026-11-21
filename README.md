# Jakarta Daily Signals

Ringkasan harian kurs USD/IDR, cuaca, dan kualitas udara Jakarta, plus peringatan Telegram saat ada anomali.

Status: **Tahap 9 (workflow harian GitHub Actions)**. Rencana lengkap ada di [docs/PLAN.md](docs/PLAN.md).

Alur harian (07:17 WIB, [.github/workflows/daily.yml](.github/workflows/daily.yml)):
Frankfurter + Open-Meteo → dlt (merge) → Neon Postgres → dbt build → ringkasan Telegram.

## Menjalankan lokal

```powershell
uv sync                 # instal Python 3.11 env + dependensi dari uv.lock
copy .env.example .env  # lalu isi nilainya (jangan di-commit)
uv run dlt --version
uv run dbt --version
```
