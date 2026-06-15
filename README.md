# KTP OCR API

REST API untuk membaca foto KTP Indonesia dan mengekstrak semua field sebagai JSON terstruktur, menggunakan FastAPI dan GPT-4o Vision.

---

## Daftar Isi

- [Arsitektur](#arsitektur)
- [Struktur Folder](#struktur-folder)
- [Field yang Diekstrak](#field-yang-diekstrak)
- [Alur Data](#alur-data)
- [Prasyarat](#prasyarat)
- [Instalasi & Konfigurasi](#instalasi--konfigurasi)
- [Menjalankan Server](#menjalankan-server)
- [Penggunaan API](#penggunaan-api)
- [Menjalankan Tests](#menjalankan-tests)
- [Docker](#docker)
- [Catatan Penting](#catatan-penting)

---

## Arsitektur

Sistem ini adalah API stateless — tidak ada database, tidak ada penyimpanan file. Setiap request diproses sepenuhnya di memori.

```
Client (cURL / Postman / Swagger UI)
         │
         ▼  POST /ocr/extract
         │  Content-Type: multipart/form-data
         │
┌────────────────────────────────────────┐
│             FastAPI App                │
│                                        │
│  ┌─────────────────────────────────┐   │
│  │  Router: /ocr/extract           │   │
│  │  • Validasi MIME type           │   │
│  │  • Validasi ukuran file (≤5MB)  │   │
│  └──────────────┬──────────────────┘   │
│                 │                      │
│  ┌──────────────▼──────────────────┐   │
│  │  ImagePreprocessor              │   │
│  │  • Decode & validasi gambar     │   │
│  │  • Konversi ke RGB              │   │
│  │  • Resize ke maks 1600×1000     │   │
│  │  • Deskew (koreksi rotasi)      │   │
│  │  • Sharpness & contrast boost   │   │
│  │  • Encode ke JPEG               │   │
│  └──────────────┬──────────────────┘   │
│                 │                      │
│  ┌──────────────▼──────────────────┐   │
│  │  KTPExtractor                   │   │
│  │  • Encode gambar ke base64      │   │
│  │  • Kirim ke OpenAI GPT-4o Vision│   │
│  │  • Parse JSON terstruktur       │   │
│  └──────────────┬──────────────────┘   │
│                 │                      │
│  ┌──────────────▼──────────────────┐   │
│  │  KTPData (Pydantic)             │   │
│  │  • Validasi NIK (16 digit)      │   │
│  │  • Normalisasi gender           │   │
│  │  • Uppercase blood type         │   │
│  └──────────────┬──────────────────┘   │
└────────────────────────────────────────┘
         │
         ▼  HTTP 200 JSON
{
  "success": true,
  "data": { "nik": "...", "nama": "...", ... },
  "model_used": "gpt-4o-2024-08-06",
  "processing_time_ms": 3241.55
}
```

### Komponen Utama

| Komponen | File | Tanggung Jawab |
|---|---|---|
| Config | `app/config.py` | Load env vars via pydantic-settings |
| Exceptions | `app/exceptions.py` | Custom exceptions + FastAPI error handlers |
| KTPData | `app/models/ktp.py` | Pydantic schema untuk 17 field KTP + validators |
| Responses | `app/models/responses.py` | Wrapper response API (OCRResponse, ErrorResponse) |
| ImagePreprocessor | `app/services/image_processor.py` | Pipeline preprocessing gambar (Pillow + OpenCV) |
| KTPExtractor | `app/services/ktp_extractor.py` | Integrasi OpenAI Vision API |
| Router | `app/routers/ocr.py` | Endpoint `POST /ocr/extract` |
| App | `app/main.py` | Factory FastAPI, CORS, exception handlers |

### Keputusan Desain

- **OpenAI Vision langsung (tanpa Tesseract)** — GPT-4o Vision lebih akurat untuk teks dengan variasi orientasi, font, dan kualitas foto. Satu API call sekaligus handle OCR + structured output.
- **`beta.chat.completions.parse` dengan Pydantic schema** — OpenAI mem-enforce JSON schema server-side, sehingga response selalu sesuai struktur `KTPData` tanpa parsing manual.
- **`temperature=0, seed=42`** — Ekstraksi adalah tugas deterministik. Foto yang sama selalu menghasilkan output yang sama.
- **Null policy ketat** — Field yang tidak terbaca dikembalikan `null`, tidak pernah ditebak. Lebih berguna bagi caller daripada nilai yang salah.
- **Stateless, in-memory** — Tidak ada disk I/O, tidak ada database. Aman untuk di-scale horizontal.

---

## Struktur Folder

```
OCR/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app factory
│   ├── config.py                # Settings dari .env
│   ├── exceptions.py            # Custom exceptions + handlers
│   ├── models/
│   │   ├── ktp.py               # KTPData Pydantic model
│   │   └── responses.py         # OCRResponse, ErrorResponse
│   ├── routers/
│   │   └── ocr.py               # POST /ocr/extract
│   └── services/
│       ├── image_processor.py   # Preprocessing pipeline
│       └── ktp_extractor.py     # OpenAI Vision integration
├── tests/
│   ├── conftest.py              # Fixtures pytest
│   ├── test_image_processor.py  # Unit tests preprocessing
│   ├── test_ktp_extractor.py    # Unit tests extractor (mocked OpenAI)
│   ├── test_ocr_endpoint.py     # Integration tests endpoint (mocked)
│   ├── test_integration.py      # Real API test (skip by default)
│   └── fixtures/
│       └── sample_ktp.jpg       # Foto KTP untuk real test (tidak di-commit)
├── .env                         # API key (gitignored)
├── .env.example                 # Template konfigurasi
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── Dockerfile
```

---

## Field yang Diekstrak

Semua field bertipe `string | null`. Dikembalikan `null` jika tidak terbaca jelas di foto.

| Field | Deskripsi | Contoh |
|---|---|---|
| `provinsi` | Provinsi dari header kartu | `"JAWA BARAT"` |
| `kota_kabupaten` | Kota/kabupaten dari header kartu | `"KOTA BANDUNG"` |
| `nik` | Nomor Induk Kependudukan (16 digit) | `"3201234567890001"` |
| `nama` | Nama lengkap (huruf kapital) | `"BUDI SANTOSO"` |
| `tempat_lahir` | Kota tempat lahir | `"BANDUNG"` |
| `tanggal_lahir` | Tanggal lahir format DD-MM-YYYY | `"15-03-1990"` |
| `jenis_kelamin` | Jenis kelamin | `"LAKI-LAKI"` atau `"PEREMPUAN"` |
| `golongan_darah` | Golongan darah | `"A"`, `"B"`, `"AB"`, atau `"O"` |
| `alamat` | Alamat jalan | `"JL. MERDEKA NO. 10"` |
| `rt_rw` | RT/RW format NNN/NNN | `"003/007"` |
| `kel_desa` | Kelurahan atau desa | `"SUKAJADI"` |
| `kecamatan` | Kecamatan | `"SUKAJADI"` |
| `agama` | Agama | `"ISLAM"` |
| `status_perkawinan` | Status perkawinan | `"BELUM KAWIN"` |
| `pekerjaan` | Pekerjaan | `"KARYAWAN SWASTA"` |
| `kewarganegaraan` | Kewarganegaraan | `"WNI"` |
| `berlaku_hingga` | Masa berlaku | `"SEUMUR HIDUP"` atau `"15-03-2030"` |

---

## Alur Data

```
1. Client upload foto KTP via multipart/form-data

2. Router validasi:
   ├── MIME type ∈ {image/jpeg, image/png, image/webp}  →  400 jika tidak
   └── Ukuran file ≤ 5MB                                →  413 jika lebih

3. ImagePreprocessor.preprocess(raw_bytes):
   ├── PIL Image.open() + verify()      →  400 jika corrupt
   ├── Konversi RGBA/P → RGB
   ├── Resize jika > 1600×1000 (LANCZOS, tidak pernah upscale)
   ├── Deskew: Canny → HoughLines → rotate (≤15°, fail-safe)
   ├── Enhance: Sharpness ×1.5, Contrast ×1.2
   └── Encode ke JPEG quality=90

4. KTPExtractor.extract(jpeg_bytes):
   ├── base64.encode(jpeg_bytes) → data URL
   ├── OpenAI beta.chat.completions.parse(
   │       model="gpt-4o",
   │       response_format=KTPData,   ← schema enforcement
   │       temperature=0, seed=42,
   │       image_detail="high"        ← full resolution tiling
   │   )
   └── Pydantic validators: NIK regex, gender normalization

5. Response HTTP 200:
   {
     "success": true,
     "data": { ...17 field KTP... },
     "model_used": "gpt-4o-2024-08-06",
     "processing_time_ms": 3241.55
   }
```

### Error Responses

| Kondisi | HTTP | `error_code` |
|---|---|---|
| MIME type tidak didukung | `400` | `INVALID_IMAGE` |
| File gambar corrupt | `400` | `INVALID_IMAGE` |
| File > 5MB | `413` | `IMAGE_TOO_LARGE` |
| OpenAI tidak bisa parse gambar | `422` | `EXTRACTION_FAILED` |
| OpenAI rate limit | `429` | `EXTRACTION_FAILED` |
| OpenAI timeout / tidak tersedia | `503` | `EXTRACTION_FAILED` |
| OpenAI API key salah | `500` | `EXTRACTION_FAILED` |

---

## Prasyarat

- Python 3.10+
- OpenAI API key (akses GPT-4o Vision)

---

## Instalasi & Konfigurasi

**1. Clone dan masuk ke direktori project:**
```bash
cd OCR
```

**2. Buat virtual environment (opsional tapi disarankan):**
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
# Untuk development + testing:
pip install -r requirements-dev.txt
```

**4. Buat file `.env`:**
```bash
cp .env.example .env
```

Edit `.env` dan isi API key:
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_TIMEOUT=60.0
OPENAI_MAX_RETRIES=2
MAX_IMAGE_SIZE_BYTES=5242880
LOG_LEVEL=INFO
```

---

## Menjalankan Server

```bash
uvicorn app.main:app --reload
```

Server berjalan di `http://localhost:8000`.

- **Swagger UI (interactive docs):** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Health check:** `http://localhost:8000/health`

---

## Penggunaan API

### `POST /ocr/extract`

Upload foto KTP dan dapatkan semua field sebagai JSON.

**Request:**
```
Content-Type: multipart/form-data
Body: file=<image file>
```

Format yang didukung: JPEG, PNG, WebP. Ukuran maksimal: 5MB.

---

**Contoh dengan cURL:**
```bash
curl -X POST http://localhost:8000/ocr/extract \
  -F "file=@/path/to/ktp.jpg"
```

**Contoh dengan Python (requests):**
```python
import requests

with open("ktp.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/ocr/extract",
        files={"file": ("ktp.jpg", f, "image/jpeg")},
    )

data = response.json()
print(data["data"]["nik"])    # "3201234567890001"
print(data["data"]["nama"])   # "BUDI SANTOSO"
```

---

**Response sukses (HTTP 200):**
```json
{
  "success": true,
  "data": {
    "provinsi": "JAWA BARAT",
    "kota_kabupaten": "KOTA BANDUNG",
    "nik": "3201234567890001",
    "nama": "BUDI SANTOSO",
    "tempat_lahir": "BANDUNG",
    "tanggal_lahir": "15-03-1990",
    "jenis_kelamin": "LAKI-LAKI",
    "golongan_darah": "A",
    "alamat": "JL. MERDEKA NO. 10",
    "rt_rw": "003/007",
    "kel_desa": "SUKAJADI",
    "kecamatan": "SUKAJADI",
    "agama": "ISLAM",
    "status_perkawinan": "BELUM KAWIN",
    "pekerjaan": "KARYAWAN SWASTA",
    "kewarganegaraan": "WNI",
    "berlaku_hingga": "SEUMUR HIDUP"
  },
  "message": "OK",
  "model_used": "gpt-4o-2024-08-06",
  "processing_time_ms": 3241.55
}
```

**Response error (contoh):**
```json
{
  "success": false,
  "error_code": "INVALID_IMAGE",
  "message": "Tipe file tidak didukung: 'application/pdf'. Yang diterima: image/jpeg, image/png, image/webp."
}
```

---

### `GET /health`

Health check untuk memastikan server berjalan.

```bash
curl http://localhost:8000/health
# {"status": "ok", "model": "gpt-4o"}
```

---

## Menjalankan Tests

**Unit tests (tanpa API key, semua di-mock):**
```bash
pytest
```

**Dengan output verbose:**
```bash
pytest -v
```

**Integration test dengan OpenAI API nyata:**

Taruh foto KTP di `tests/fixtures/sample_ktp.jpg`, lalu:
```bash
pytest -m integration -v
```

> Integration test memerlukan `OPENAI_API_KEY` yang valid di `.env`.

---

## Docker

**Build image:**
```bash
docker build -t ktp-ocr .
```

**Jalankan container:**
```bash
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... ktp-ocr
```

**Atau dengan file `.env`:**
```bash
docker run -p 8000:8000 --env-file .env ktp-ocr
```

---

## Catatan Penting

**Tips foto untuk hasil terbaik:**
- Foto KTP harus mencakup seluruh kartu
- Pencahayaan merata, hindari bayangan atau pantulan cahaya
- Foto tegak lurus (tidak terlalu miring), meskipun sistem bisa koreksi rotasi kecil ≤15°
- Resolusi minimal 800×500 pixel

**Field null vs salah:**
Field yang tidak terbaca dikembalikan `null`. Ini disengaja — lebih baik `null` yang jujur daripada nilai yang terlihat valid tapi salah.

**Privasi:**
Foto KTP adalah data pribadi yang sensitif. Pastikan transfer dilakukan via HTTPS di production, dan tidak menyimpan foto atau response ke log yang persisten.

**Estimasi biaya OpenAI:**
GPT-4o Vision dengan `detail: high` mengonsumsi sekitar 800–1500 token per gambar. Estimasi ~$0.003–0.006 per request (harga berlaku per Juni 2025).
