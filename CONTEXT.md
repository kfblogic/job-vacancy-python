# CONTEXT.md — Dokumentasi Teknis Project

## Deskripsi

**Job Vacancy Scraper API** — Aplikasi web dan REST API agregator lowongan pekerjaan dari tiga platform karir terbesar di Indonesia (Glints, JobStreet, Karir.com). Dibangun dengan Python Flask dan dioptimalkan untuk deployment di Vercel Serverless.

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Backend | Python 3.10+, Flask |
| Scraping | BeautifulSoup4, CloudScraper |
| Cache (Production) | Vercel KV / Upstash Redis (`upstash-redis`) |
| Cache (Development) | JSON file shards di `data/shards/` |
| Scheduler (Production) | Vercel Cron Jobs |
| Scheduler (Development) | APScheduler (BackgroundScheduler) |
| Deployment | Vercel Serverless Functions (`@vercel/python`) |

## Struktur Direktori

```
skripsi/
├── config/                   # Cookie files anti-bot per platform
│   ├── glints.json
│   ├── jobstreet.json
│   ├── karir.json
│   └── rf.json
├── data/
│   └── shards/               # Cache lokal (hanya development, diabaikan di Vercel)
│       ├── programmer.glints.json
│       ├── programmer.jobstreet.json
│       └── programmer.karir.json
├── helpers/
│   ├── cookie_helper.py      # Load cookie JSON → RequestsCookieJar
│   └── response.py           # ResponseHelper: success_response / failure_response
├── singletons/
│   └── cloudscrapper.py      # Singleton CloudScraper dengan cookie management
├── templates/
│   └── index.html            # Frontend portal pencarian kerja
├── cache.py                  # Hybrid cache: Vercel KV (Redis) ↔ file lokal
├── main.py                   # Flask app, routing, scheduler, cron security
├── scraper.py                # Scraper engine: Glints, JobStreet, Karir.com
├── utils.py                  # normalize_scraper_result, slugify helpers
├── requirements.txt          # Python dependencies
├── vercel.json               # Vercel: builds, routes, cron jobs
├── .vercelignore             # Files yang diabaikan saat deploy
├── AGENTS.md                 # Instruksi untuk AI coding agent
├── CONTEXT.md                # Dokumen ini
└── README.md                 # Dokumentasi utama project
```

## Alur Data (Data Flow)

```
User Request (GET /glints?work=Programmer&page=1)
    │
    ├─→ get_variant() → cache.py
    │       ├─→ [HIT]  Redis/File → Return cached data
    │       └─→ [MISS] Continue to scraper
    │
    ├─→ scraper.search_glints() → scraper.py
    │       ├─→ CloudScraper + cookies → HTTP request ke Glints
    │       ├─→ BeautifulSoup parse HTML / GraphQL response
    │       └─→ Return normalized job list
    │
    ├─→ put_variant() → cache.py
    │       ├─→ Redis (Vercel) atau File JSON (lokal)
    │       └─→ TTL: 24 jam freshness, 7 hari Redis key expiry
    │
    └─→ JSON Response ke client
```

## API Endpoints

### Public Endpoints

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/` | Halaman web portal pencarian kerja |
| GET | `/glints` | Cari lowongan dari Glints |
| GET | `/jobstreet` | Cari lowongan dari JobStreet |
| GET | `/karir` | Cari lowongan dari Karir.com |
| GET | `/all` | Agregasi dari semua sumber sekaligus |

### Admin Endpoints

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/admin/refresh` | Refresh semua cache shard (dilindungi CRON_SECRET di Vercel) |

### Query Parameters

| Parameter | Default | Deskripsi |
|---|---|---|
| `work` | `Programmer` | Kata kunci pencarian pekerjaan |
| `job_type` | `""` | Filter tipe: `fulltime`, `parttime`, `kontrak`, `freelance`, `magang` |
| `work_option` | `""` | Filter lokasi kerja: `onsite`, `remote`, `hybird` |
| `location_id` | `all` | Filter lokasi (Glints only): `jakarta`, `surabaya`, dll |
| `page` | `1` | Nomor halaman |
| `per_page` | `24` | Jumlah job per halaman (endpoint `/all` saja) |
| `debug` | `0` | Tampilkan info debug jika `1` |

## Sistem Cache

### Hierarki Prioritas
1. **Vercel KV (Redis)** — Jika `KV_REST_API_URL` dan `KV_REST_API_TOKEN` tersedia
2. **File JSON lokal** — Jika tidak ada Redis dan BUKAN di Vercel
3. **Shard kosong (in-memory)** — Jika di Vercel tanpa Redis (graceful degradation)

### Key Format
- Redis: `shard:{keyword_slug}:{source}` (contoh: `shard:programmer:glints`)
- File: `data/shards/{keyword_slug}.{source}.json` (contoh: `programmer.glints.json`)

### TTL (Time-To-Live)
- **Variant freshness**: 24 jam — setelah itu dianggap stale dan akan di-fetch ulang
- **Redis key expiry**: 7 hari — shard yang tidak diakses akan dihapus otomatis oleh Redis

## Scheduler & Cron

### Development (Lokal)
- `APScheduler` (BackgroundScheduler) berjalan sebagai background thread
- Interval: setiap 24 jam, refresh semua shard yang stale
- Dijalankan otomatis saat `python main.py`

### Production (Vercel)
- APScheduler **dinonaktifkan** (`IS_VERCEL` check di `start_scheduler()`)
- Digantikan oleh **Vercel Cron Jobs** yang dikonfigurasi di `vercel.json`
- Schedule: `0 0 * * *` (setiap hari pukul 00:00 UTC)
- Target: `GET /admin/refresh` dengan header `Authorization: Bearer {CRON_SECRET}`

## Environment Variables

| Variable | Wajib di Vercel? | Keterangan |
|---|---|---|
| `KV_REST_API_URL` | Ya (untuk cache) | URL REST API Vercel KV, otomatis terisi saat menghubungkan KV Storage |
| `KV_REST_API_TOKEN` | Ya (untuk cache) | Token autentikasi Vercel KV |
| `CRON_SECRET` | Direkomendasikan | Token keamanan untuk proteksi endpoint `/admin/refresh` |
| `VERCEL` | Otomatis | Diset `"1"` secara otomatis oleh Vercel saat runtime |
| `SCRAPER_SHARDS_DIR` | Tidak | Override path folder cache lokal (development only) |

## Catatan Penting

### Vercel Serverless Constraints
- **Filesystem read-only** di `/var/task/` — semua operasi tulis disk harus dihindari
- **Stateless** — tidak ada state yang bertahan antar request
- **Execution timeout** — ~10 detik (free tier), ~60 detik (pro tier)
- **Cold start** — instance baru bisa mengalami delay saat pertama kali dipanggil

### Anti-Bot / Scraping
- CloudScraper digunakan untuk bypass Cloudflare
- Cookie files di `config/` mungkin perlu diperbarui secara berkala jika expired
- IP data center (AWS/Vercel) berisiko diblokir oleh platform target — pertimbangkan proxy jika terjadi error 403
