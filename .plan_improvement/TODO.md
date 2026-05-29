# TODO: Rencana Penyempurnaan Provider Gateway (Multi-Provider) Hermes Agent

> **Status Terakhir:**
> - **Fondasi Observabilitas:** Selesai 100% (Production-Grade SQLite, WAL Mode, Schema Versioning, Time-Window Query).
> - **Test Suite:** 55 skenario uji lulus 100% dalam 0.55 detik (`pytest tests/provider_gateway -q` ✅).
> - **Desain:** Default-off tetap terjaga penuh. Blast radius runtime terkontrol (tidak ada breaking change).

---

## PETA JALAN & DAFTAR TUGAS (TODO LIST)

### 📌 FASE 1: Fondasi Observabilitas & Pelacakan Penggunaan
*Fase ini meletakkan fondasi penyimpanan, pelaporan, versi skema, dan mitigasi konkurensi database.*

- [x] **Infrastruktur SQLite Aman Konkurensi:**
  - [x] Implementasi helper `_connect()` terpusat dengan mode WAL (*Write-Ahead Logging*).
  - [x] Mengatur `synchronous = NORMAL` untuk kinerja tulis cepat dan aman.
  - [x] Mengatur `busy_timeout = 5000` (5 detik) untuk mencegah kegagalan `SQLITE_BUSY` saat penulisan bersamaan.
- [x] **Schema Versioning & Perlindungan Migrasi Masa Depan:**
  - [x] Menambahkan versi skema tingkat modul `SCHEMA_VERSION = 1` di `usage_tracker.py` dan mengekspornya di `__init__.py`.
  - [x] Membuat tabel `provider_usage_schema_version` untuk mencatat tanggal penerapan skema secara idempotent.
  - [x] Verifikasi fungsionalitas re-open database tidak melipatgandakan catatan versi.
- [x] **Time-Window Query & Parameterisasi:**
  - [x] Menambahkan parameter opsional `since` dan `until` (Unix timestamp) pada method `summarize_by_provider()`.
  - [x] Query aman dari SQL Injection menggunakan parameterisasi SQL SQLite standard.
- [x] **Cost Tracking Pipeline & Normalisasi:**
  - [x] Menambahkan integrasi pengujian fungsional penaksiran biaya token.
  - [x] Memperbaiki bug parsing input/output token untuk model non-OpenAI (seperti Anthropic `input_tokens`/`output_tokens`).
- [x] **Pengujian Komprehensif (Ekspansi Pengujian):**
  - [x] Meningkatkan cakupan unit test dari 24 menjadi 55 test di seluruh 5 file pengujian (`test_config`, `test_usage_tracker`, `test_runtime`, `test_policy`, `test_status`).
- [x] **CLI Visibility Surface (`/usage`):**
  - [x] Hook status diletakkan pada runtime CLI di `cli.py` agar ringkasan statistik penggunaan dapat diakses tanpa mengaktifkan perutean aktif.

---

### 📌 FASE 2: Perutean Aktif (Active Routing Engine) & Ketahanan (Resilience)
*Tujuan: Mengaktifkan pengalihan otomatis ke provider alternatif dan memantau kesehatan provider secara real-time.*

- [ ] **Circuit Breaker Multi-Provider (`circuit_breaker.py`):**
  - [ ] Implementasikan state machine thread-safe: `CLOSED`, `OPEN`, `HALF_OPEN`.
  - [ ] Mencatat kegagalan berturut-turut (*consecutive failures*) per provider sebelum memblokir request.
  - [ ] Mendukung waktu cooldown eksponensial (*exponential backoff cooldown*) sebelum mencoba status `HALF_OPEN`.
  - [ ] Buat unit test isolasi untuk skenario kegagalan, sukses, pemulihan, dan multi-threading.
- [ ] **Routing Engine & Weighted Scoring (`router.py`):**
  - [ ] Membuat algoritma pemilihan berbasis bobot (*weighted scoring*) dengan 6 faktor (kesehatan, biaya, latensi P50, sisa kuota, prioritas user, stabilitas historis).
  - [ ] Mendukung *exploration rate* dinamis (misal: 5% kemungkinan memilih provider acak yang sehat untuk pembaruan metrik latensi baru).
- [ ] **Integrasi dengan Runtime Agent (`agent/conversation_loop.py`):**
  - [ ] Hubungkan `ProviderRouter` dengan loop failover Hermes di `_try_activate_fallback()`.
  - [ ] **[PENTING]** Lakukan penyelarasan agar tidak menduplikasi logika pembuatan client, penanganan cache prompt, dan kompresi konteks yang sudah ditangani dengan baik oleh Hermes.
  - [ ] Tambahkan konfigurasi gate baru: `provider_gateway.routing.mode: observe | active` (default: `observe` agar tetap aman).
- [ ] **Penyedia LiteLLM (Opt-in Multi-Provider Backend):**
  - [ ] Tambahkan `litellm` sebagai dependency opsional di `pyproject.toml` (extras: `gateway`).
  - [ ] Buat wrapper adapter tipis di `provider_gateway/litellm_backend.py` untuk mengarahkan panggilan ke API LiteLLM jika diaktifkan.

---

### 📌 FASE 3: Optimasi Pesan, Cache, & Observabilitas Lanjutan
*Tujuan: Menghemat token, biaya, dan memberikan pelacakan yang lebih mendalam.*

- [ ] **Pelacakan Penggunaan untuk Mode Streaming:**
  - [ ] Menambahkan penyadapan (*interception*) usage token pada respon streaming (`chat_completions` stream) tanpa mengganggu rendering output TUI/CLI.
- [ ] **Kompresi Token (Token Compression / RTK):**
  - [ ] Mengintegrasikan logika pemangkasan pesan sistem atau kompresi riwayat obrolan panjang untuk mengurangi penggunaan token prompt pada context window LLM.
- [ ] **Semantic Cache Engine:**
  - [ ] Menyediakan in-memory cache berbasis pencarian semantik (vektor similarity) lokal atau via Redis.
  - [ ] Menghindari pengiriman request LLM yang identik untuk menghemat biaya operasional secara instan.
- [ ] **Pelacakan Batas Kuota (Quota Tracking):**
  - [ ] Menambahkan batas pengeluaran harian/bulanan (dalam USD atau Token) per model/provider.
  - [ ] Melarang pengiriman request jika kuota telah terlampaui dan langsung berpindah ke provider gratis/lokal.

---

### 📌 FASE 4: Ekosistem, Guardrails, & Keamanan
*Tujuan: Menjamin keamanan kredensial dan memperluas dukungan ke edge deployment.*

- [ ] **Secure Credential Store:**
  - [ ] Jangan gunakan pengodean base64 biasa untuk menyimpan API key tambahan.
  - [ ] Hubungkan dengan pustaka `keyring` bawaan OS atau gunakan enkripsi AES lokal dengan kunci rahasia yang di-generate per mesin.
- [ ] **Dukungan Provider Lokal (Ollama / Local Model Integration):**
  - [ ] Mempermudah auto-discovery model Ollama lokal yang berjalan secara default sebagai fallback bebas biaya.
- [ ] **Penyaringan Konten & PII Sanitizer (Guardrails):**
  - [ ] Deteksi otomatis dan anonimisasi data sensitif (seperti password, token, informasi pribadi) sebelum dikirim ke server cloud pihak ketiga.
- [ ] **OpenAI-Compatible Local Endpoint:**
  - [ ] Menyediakan mini local API server di dalam Hermes agar aplikasi atau CLI pihak ketiga lainnya dapat menggunakan sistem perutean multi-provider pintar Hermes.

---

## 🛠️ INSTRUKSI BAGI TIM / AGENT BERIKUTNYA

Saat Anda mengambil alih tugas ini untuk memulai **Fase 2 (Circuit Breaker & Routing)**:

1. **Jalankan Uji Coba Terlebih Dahulu:**
   Pastikan fondasi awal berfungsi penuh dengan mengetikkan:
   ```bash
   uv run --extra dev python -m pytest tests/provider_gateway -q
   ```
2. **Desain Circuit Breaker:**
   Mulailah dengan membuat `provider_gateway/circuit_breaker.py`. Buatlah sesederhana mungkin menggunakan `threading.Lock` untuk menjamin keamanan dari race condition. Pastikan tidak ada dependensi eksternal tambahan selain SQLite.
3. **Harmonisasi `_try_activate_fallback`:**
   Sebelum memodifikasi `agent/conversation_loop.py`, baca fungsi tersebut secara utuh. Fungsi tersebut berukuran besar dan bertanggung jawab atas siklus hidup koneksi, kredensial, dan timeout. Lakukan integrasi secara modular dengan membungkus logika pemanggilan provider berikutnya melalui perutean dinamis kita.
