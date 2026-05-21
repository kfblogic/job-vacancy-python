# AGENTS.md — Panduan untuk AI Coding Agent

Dokumen ini berisi instruksi konteks bagi AI coding assistant yang bekerja pada project ini.

## Tentang Project

Project ini adalah **Job Vacancy Scraper & API** berbasis **Python Flask** yang mengagregasi data lowongan kerja dari tiga sumber: **Glints**, **JobStreet**, dan **Karir.com**. Project ini dideploy sebagai **Vercel Serverless Functions**.

## Arsitektur

```
main.py          → Entry point Flask, routing API, scheduler
scraper.py       → Mesin scraper (Glints GraphQL/HTML, JobStreet HTML, Karir API)
cache.py         → Sistem cache hybrid: Vercel KV (Redis) + fallback file lokal
utils.py         → Helper: normalize response, slugify
helpers/         → Cookie loader, ResponseHelper class
singletons/      → Singleton CloudScraper instance
templates/       → Frontend HTML (index.html)
config/          → Cookie files per-platform (JSON)
```

## Aturan Penting

### Vercel Serverless Constraints
- **Filesystem read-only**: Jangan pernah melakukan `os.makedirs()`, `open(..., 'w')`, atau operasi tulis disk lainnya tanpa mengecek `IS_VERCEL` terlebih dahulu. Gunakan Vercel KV (Redis) sebagai storage utama di production.
- **Stateless**: Setiap request berjalan di instance terpisah. Jangan mengandalkan variabel global in-memory antar request.
- **No background threads**: `BackgroundScheduler` dimatikan di Vercel. Gunakan Vercel Cron Jobs (dikonfigurasi di `vercel.json`) untuk penjadwalan.
- **Max execution time**: Serverless function Vercel memiliki batas waktu eksekusi (~10 detik di free tier). Pastikan scraping selesai dalam batas waktu ini.

### Cache System (`cache.py`)
- Deteksi environment: `IS_VERCEL = os.environ.get("VERCEL") == "1"`
- Prioritas storage: Redis (`redis_client`) → filesystem lokal (hanya saat development)
- Di Vercel tanpa KV: mengembalikan shard kosong, **tidak mencoba menulis ke disk**
- Redis key format: `shard:{keyword_slug}:{source}`
- TTL shard di Redis: 7 hari. TTL variant freshness: 24 jam.

### Scraper (`scraper.py`)
- Menggunakan `cloudscraper` untuk bypass Cloudflare protection
- Cookie files disimpan di `config/*.json`
- Debug write ke `test.txt` dibungkus `try/except OSError` agar aman di Vercel
- Response selalu dikembalikan melalui `ResponseHelper` (helpers/response.py)

### Response Format
Semua endpoint mengembalikan JSON dengan struktur:
```json
{
  "status": "success" | "failed",
  "message": "...",
  "data": {
    "jobs": [...],
    "pagination": {
      "current_page": 1,
      "last_page": 5,
      "has_next": true
    }
  }
}
```

### Environment Variables (Vercel)
| Variable | Keterangan |
|---|---|
| `KV_REST_API_URL` | URL koneksi Vercel KV (otomatis dari Vercel Storage) |
| `KV_REST_API_TOKEN` | Token autentikasi Vercel KV |
| `CRON_SECRET` | Token keamanan untuk endpoint `/admin/refresh` |
| `VERCEL` | Diset `"1"` otomatis oleh Vercel saat runtime |

### Testing
- Jalankan lokal: `python main.py` (port 5050)
- Verifikasi sintaks: `python -m py_compile main.py cache.py scraper.py`
- Debug mode: tambahkan `?debug=1` pada URL endpoint API

### Konvensi Kode
- Bahasa komentar: **Bahasa Indonesia**
- Bahasa variabel/fungsi: **Bahasa Inggris**
- Framework: Flask (tanpa blueprint, single-file routing di `main.py`)
- Tidak menggunakan ORM — data disimpan sebagai JSON dict
