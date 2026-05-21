# Job Scraper API & Portal (Glints, JobStreet, Karir.com)

Aplikasi portal pencarian dan REST API agregator lowongan pekerjaan berbasis **Python Flask**. Project ini dirancang khusus untuk mempermudah pencarian lowongan kerja terintegrasi dari tiga platform karir terbesar di Indonesia: **Glints**, **JobStreet**, dan **Karir.com** secara real-time.

Aplikasi ini sudah dioptimalkan dan siap dideploy secara instan ke **Vercel Serverless** dengan dukungan caching performa tinggi menggunakan **Vercel KV (Redis)** serta penjadwalan otomatis via **Vercel Cron Jobs**.

---

## ✨ Fitur Utama

- **Multi-Source Real-time Scraping**: Scraper handal untuk mengekstrak data pekerjaan dari Glints (GraphQL/HTML), JobStreet (HTML), dan Karir.com (API).
- **Unified & Deduplicated API Endpoint (`/all`)**: Endpoint agregasi yang menggabungkan hasil pencarian dari ketiga sumber sekaligus, menyaring data duplikat, dan mengembalikan skema data terpadu lengkap dengan *pagination*.
- **Anti-Bot Bypass**: Menggunakan `cloudscraper` terintegrasi dengan penanganan cookies dinamis untuk melewati proteksi keamanan bot (seperti Cloudflare).
- **Hybrid High-Performance Cache**:
  - **Produksi (Vercel KV / Redis)**: Caching serverless stateless yang sangat cepat.
  - **Lokal (File System)**: Penyimpanan cache otomatis berbentuk file `.json` (*sharding*) jika dijalankan secara lokal (offline-first).
- **Cloud-Native Automated Scheduler**:
  - Memicu penyegaran data otomatis secara berkala menggunakan **Vercel Cron Jobs** di serverless.
  - Menggunakan thread scheduler bawaan (`APScheduler`) saat dijalankan di komputer lokal.
- **Sleek Web Interface**: Halaman dashboard interaktif berbasis template HTML/CSS untuk kemudahan pencarian langsung oleh pengguna.

---

## 🛠️ Tech Stack

- **Core**: Python 3.10+
- **Framework**: Flask
- **Scraping & Parser**: BeautifulSoup4, CloudScraper
- **Database / Cache**: Vercel KV (Redis) / Local File Shard
- **Scheduler**: Vercel Cron Jobs / APScheduler
- **Deployment Platform**: Vercel Serverless

---

## 📂 Struktur Project

```text
├── config/                # Berkas konfigurasi & cookies anti-bot (glints, jobstreet, karir)
├── data/shards/           # Folder cache lokal (diabaikan saat deploy di Vercel)
├── helpers/               # Helper untuk parsing cookie & standardisasi response API
├── templates/             # Halaman web frontend (index.html)
├── singletons/            # Singleton class untuk inisialisasi cloudscraper
├── cache.py               # Logika manajemen cache hybrid (Vercel KV & Lokal)
├── scraper.py             # Mesin scraper utama untuk Glints, JobStreet, dan Karir.com
├── main.py                # Entry point server Flask, routing API, dan scheduler
├── requirements.txt       # Dependencies Python
├── vercel.json            # Konfigurasi deploy, routing, & cron scheduling Vercel
└── .vercelignore          # File pengecualian saat proses upload ke Vercel
```

---

## 🚀 Cara Menjalankan Secara Lokal (Offline)

1. **Clone Repositori**:
   ```bash
   git clone https://github.com/username/nama-repo.git
   cd nama-repo
   ```

2. **Buat & Aktifkan Virtual Environment** (Opsional tapi disarankan):
   ```bash
   python -m venv venv
   # Di Windows:
   .\venv\Scripts\activate
   # Di macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Jalankan Aplikasi**:
   ```bash
   python main.py
   ```
   Aplikasi akan berjalan di `http://127.0.0.1:5050`.

---

## 📡 Daftar Endpoint API

### 1. Halaman Dashboard Web
- **Endpoint**: GET `/`
- **Deskripsi**: Portal pencarian kerja interaktif.

### 2. API Pencarian Spesifik Sumber
- **Glints**: GET `/glints?work=Programmer&page=1`
- **JobStreet**: GET `/jobstreet?work=Programmer&page=1`
- **Karir.com**: GET `/karir?work=Programmer&page=1`
- **Parameter**:
  - `work` (default: `Programmer`): Kata kunci pekerjaan.
  - `job_type`: Filter tipe pekerjaan (`fulltime`, `parttime`, `kontrak`, `freelance`).
  - `work_option`: Filter lokasi kerja (`onsite`, `remote`, `hybird`).
  - `page` (default: `1`): Nomor halaman.

### 3. API Agregasi Terpadu (All Sources)
- **Endpoint**: GET `/all?work=Programmer&page=1`
- **Deskripsi**: Mengambil data dari Glints, JobStreet, dan Karir secara bersamaan, melakukan penggabungan, penyaringan duplikat secara cerdas, dan pengembalian dengan skema data seragam.

### 4. API Penyegaran Cache (Admin Only)
- **Endpoint**: GET `/admin/refresh`
- **Deskripsi**: Endpoint manual / terjadwal untuk memperbarui cache shard yang telah kedaluwarsa. Dilindungi oleh otentikasi token `CRON_SECRET` saat berjalan di Vercel.

---

## ☁️ Langkah Deployment ke Vercel

1. **Hubungkan Repositori ke Vercel**:
   - Buat project baru di [Vercel](https://vercel.com/) dan impor repositori GitHub Anda.
2. **Sambungkan Vercel KV (Redis)**:
   - Masuk ke tab **Storage** pada dashboard project Vercel Anda.
   - Buat database baru tipe **KV (Redis)** dan hubungkan ke project Anda. Kredensial `KV_REST_API_URL` dan `KV_REST_API_TOKEN` akan otomatis terkonfigurasi.
3. **Konfigurasi Variabel Keamanan Cron (Sangat Direkomendasikan)**:
   - Tambahkan Environment Variable baru di pengaturan Vercel:
     - **Key**: `CRON_SECRET`
     - **Value**: *[Buat string password acak yang kuat]*
   - Token ini secara otomatis dipakai oleh sistem Vercel Cron untuk memverifikasi keamanan endpoint `/admin/refresh` Anda.
4. **Deploy**:
   - Vercel akan otomatis mendeteksi `vercel.json` dan men-deploy project Anda sebagai Serverless Functions yang siap digunakan secara publik!
