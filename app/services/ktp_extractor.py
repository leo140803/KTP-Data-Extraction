import base64
from typing import Tuple

from openai import (
    OpenAI,
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
)

from app.config import settings
from app.exceptions import KTPExtractionError
from app.models.ktp import KTPData

SYSTEM_PROMPT = """Kamu adalah mesin OCR presisi yang khusus membaca KTP (Kartu Tanda Penduduk) Indonesia.

Tugasmu adalah mengekstrak semua field teks yang terlihat dari gambar KTP yang diberikan. Ikuti aturan berikut dengan ketat:

1. Ekstrak HANYA yang terlihat jelas di gambar. JANGAN menebak, menyimpulkan, atau mengarang nilai.
2. Jika suatu field tertutup, rusak, buram, atau tidak ada — kembalikan null untuk field tersebut.
3. NIK harus tepat 16 digit. Jika tidak bisa membaca semua 16 digit dengan yakin, kembalikan null untuk NIK.
4. Tanggal harus dalam format DD-MM-YYYY. Konversi jika kamu melihat format lain.
5. Jenis Kelamin harus tepat "LAKI-LAKI" atau "PEREMPUAN".
6. RT/RW harus diformat sebagai "NNN/NNN" (contoh: "003/007").
7. Transkripsi nama dan alamat persis seperti yang tercetak (huruf kapital, jangan dinormalisasi).
8. Provinsi dan Kota/Kabupaten berasal dari teks header di bagian atas kartu (di atas tulisan "KARTU TANDA PENDUDUK").
9. Berlaku Hingga bisa berupa tanggal (DD-MM-YYYY) atau teks "SEUMUR HIDUP".
10. Kembalikan semua nilai string dalam HURUF KAPITAL sesuai yang tertera di kartu."""

USER_PROMPT = """Tolong ekstrak semua field KTP dari gambar kartu tanda penduduk Indonesia ini.
Kembalikan null untuk field apapun yang tidak bisa kamu baca dengan yakin."""


class KTPExtractor:
    def __init__(self):
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout,
            max_retries=settings.openai_max_retries,
        )

    def extract(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Tuple[KTPData, str]:
        """
        Kirim gambar yang sudah dipreproses ke OpenAI Vision dan parse data KTP terstruktur.
        Mengembalikan (KTPData, model_id_yang_digunakan).
        Raise KTPExtractionError jika ada kegagalan.
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{image_b64}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        try:
            completion = self._client.beta.chat.completions.parse(
                model=settings.openai_model,
                messages=messages,
                response_format=KTPData,
                temperature=0,
                seed=42,
            )
        except AuthenticationError:
            raise KTPExtractionError(
                "OpenAI API key tidak valid. Periksa konfigurasi OPENAI_API_KEY.",
                status_code=500,
            )
        except RateLimitError:
            raise KTPExtractionError(
                "OpenAI rate limit tercapai. Coba lagi beberapa saat.",
                status_code=429,
            )
        except APITimeoutError:
            raise KTPExtractionError(
                "Request ke OpenAI timeout. Coba lagi.",
                status_code=503,
            )
        except APIConnectionError as e:
            raise KTPExtractionError(
                f"Tidak bisa terhubung ke OpenAI API: {e}",
                status_code=503,
            )

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise KTPExtractionError(
                "OpenAI tidak bisa mengekstrak data terstruktur dari gambar ini. "
                "Pastikan gambar adalah foto KTP yang jelas.",
                status_code=422,
            )

        return parsed, completion.model
