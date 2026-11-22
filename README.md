# Jakarta Daily Signals

Ringkasan harian kurs USD/IDR, cuaca, dan kualitas udara Jakarta, plus peringatan Telegram saat ada anomali.

Status: **Tahap 10 (CI di setiap PR)**. Rencana lengkap ada di [docs/PLAN.md](docs/PLAN.md).

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)): ruff + sqlfluff + pytest + `dbt parse`,
lalu `dbt build` ke schema sementara `ci_pr_<n>_*` di Neon branch dev (dihapus setelah run).

Alur harian (07:17 WIB, [.github/workflows/daily.yml](.github/workflows/daily.yml)):
Frankfurter + Open-Meteo → dlt (merge) → Neon Postgres → dbt build → ringkasan Telegram.

## Menjalankan lokal

```powershell
uv sync                 # instal Python 3.11 env + dependensi dari uv.lock
copy .env.example .env  # lalu isi nilainya (jangan di-commit)
uv run dlt --version
uv run dbt --version
```
