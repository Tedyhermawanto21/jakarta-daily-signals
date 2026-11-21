"""Jakarta Daily Signals: pipeline harian kurs, cuaca, dan kualitas udara Jakarta."""

import os

__version__ = "0.1.0"

# dlt mengirim telemetri anonim ke dltHub secara default. Proyek ini mematikannya untuk
# semua entrypoint (lokal, test, GitHub Actions). setdefault: masih bisa di-override lewat env.
# Harus diset sebelum dlt membaca konfigurasi, jadi ditaruh di __init__ paket.
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
