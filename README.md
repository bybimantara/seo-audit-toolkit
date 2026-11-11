# 🔍 SEO Audit Toolkit

Toolkit komprehensif untuk menganalisis, mengaudit, dan mengoptimalkan SEO situs web — mulai dari audit teknis (*crawlability*, *indexability*, *Core Web Vitals*), struktur data (*Schema.org*), kualitas konten (*E-E-A-T*), hingga kesiapan *AI Search / Generative Engine Optimization (GEO)*.

---

## ✨ Fokus Utama

- **Technical SEO Audit**: Pemeriksaan *robots.txt*, *sitemap.xml*, status HTTP, *canonical tags*, struktur URL, dan *Core Web Vitals*.
- **On-Page & Content Audit**: Evaluasi *meta tags*, struktur *heading* (`H1`–`H6`), kualitas konten (*E-E-A-T*), dan optimasi gambar.
- **Structured Data & Schema**: Validasi dan pembuatan *JSON-LD Schema.org* untuk *Rich Results*.
- **AI Search / GEO Readiness**: Analisis keterbacaan untuk *crawler* AI, *llms.txt*, dan optimasi sitasi pada mesin pencari berbasis AI.

---

## 📂 Struktur Repositori

```text
seo-audit-toolkit/
├── src/seo_audit/        # Core engine (analyzer, crawler, models, reporters, web, cli)
├── tests/                # Automated unit & integration tests
├── docs/                 # Dokumentasi internal (PRD, contract, plan, progress, dll.)
├── .env.example          # Template konfigurasi environment (tanpa secret)
├── .gitignore            # Pengecualian berkas Git & dokumen internal agent
├── LICENSE               # Lisensi proyek
├── pyproject.toml        # Konfigurasi package, tool uv & pytest
└── README.md             # Dokumentasi utama proyek
```

---

## ⚡ Cara Menjalankan

### 1. Audit via CLI
Jalankan audit langsung ke target URL dari terminal:
```bash
uv run seo-audit https://example.com --max-pages 50 --csv report.csv --html report.html
```

### 2. Jalankan Web Dashboard
Jalankan web server lokal untuk audit interaktif melalui browser:
```bash
uv run seo-audit serve --reload
```
Buka browser di `http://127.0.0.1:8000`.

### 3. Menjalankan Pengujian (Testing)
```bash
uv run pytest
```

---

## 🚀 Persiapan Awal (Getting Started)

1. **Clone repositori**:
   ```bash
   git clone https://github.com/bybimantara/seo-audit-toolkit.git
   cd seo-audit-toolkit
   ```

2. **Konfigurasi Environment**:
   Salin berkas `.env.example` menjadi `.env` dan sesuaikan variabel yang dibutuhkan:
   ```bash
   cp .env.example .env
   ```

---

## 📄 Lisensi

Didistribusikan di bawah lisensi yang tertera pada berkas [LICENSE](./LICENSE).

