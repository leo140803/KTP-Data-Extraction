import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class KTPData(BaseModel):
    """
    Semua field KTP Indonesia. Semua Optional — kembalikan None jika tidak terbaca jelas.
    Model ini digunakan sebagai response_format ke OpenAI (schema enforcement)
    sekaligus sebagai response body API.
    """

    # Header kartu (bagian atas)
    provinsi: Optional[str] = Field(None, description="Nama provinsi dari header kartu")
    kota_kabupaten: Optional[str] = Field(None, description="Kota/kabupaten dari header kartu")

    # Identitas utama
    nik: Optional[str] = Field(None, description="Nomor Induk Kependudukan, 16 digit")
    nama: Optional[str] = Field(None, description="Nama lengkap sesuai kartu (huruf kapital)")
    tempat_lahir: Optional[str] = Field(None, description="Kota tempat lahir")
    tanggal_lahir: Optional[str] = Field(None, description="Tanggal lahir format DD-MM-YYYY")
    jenis_kelamin: Optional[str] = Field(None, description="LAKI-LAKI atau PEREMPUAN")
    golongan_darah: Optional[str] = Field(None, description="Golongan darah: A, B, AB, atau O")

    # Blok alamat
    alamat: Optional[str] = Field(None, description="Alamat jalan")
    rt_rw: Optional[str] = Field(None, description="RT/RW format NNN/NNN")
    kel_desa: Optional[str] = Field(None, description="Nama kelurahan atau desa")
    kecamatan: Optional[str] = Field(None, description="Nama kecamatan")

    # Field administratif
    agama: Optional[str] = Field(None, description="Agama")
    status_perkawinan: Optional[str] = Field(None, description="Status perkawinan")
    pekerjaan: Optional[str] = Field(None, description="Pekerjaan")
    kewarganegaraan: Optional[str] = Field(None, description="Kewarganegaraan, biasanya WNI")
    berlaku_hingga: Optional[str] = Field(
        None, description="Tanggal berlaku (DD-MM-YYYY) atau SEUMUR HIDUP"
    )

    @field_validator("nik")
    @classmethod
    def validate_nik(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = re.sub(r"[\s\-.]", "", v.strip())
        if not re.match(r"^\d{16}$", cleaned):
            return None
        return cleaned

    @field_validator("jenis_kelamin")
    @classmethod
    def normalize_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_upper = v.strip().upper()
        if v_upper in {"LAKI-LAKI", "LAKI", "L"}:
            return "LAKI-LAKI"
        if v_upper in {"PEREMPUAN", "P"}:
            return "PEREMPUAN"
        return v_upper

    @field_validator("golongan_darah")
    @classmethod
    def normalize_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().upper()
