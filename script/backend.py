"""
backend.py — FlightPredictor
Modul utama yang menangani lookup data historis, encoding, dan prediksi harga tiket.

v2: Free Routing — semua kombinasi bandara_asal × bandara_tujuan yang valid
    di model_columns dapat diprediksi, bukan hanya rute yang ada di data historis.
    Untuk rute baru, jarak_km dihitung dengan haversine dan fitur lain
    diambil dari profil maskapai/kelas yang paling relevan.
"""

import math
import os
import warnings
from datetime import datetime, date, timedelta

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Path Helpers
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "data")
_ARTIFACT_DIR = os.path.join(_BASE_DIR, "artifact")

# ---------------------------------------------------------------------------
# Koordinat bandara (lat, lon) — dari airports.csv via iata_code
# Digunakan untuk menghitung jarak_km haversine pada rute baru
# ---------------------------------------------------------------------------

AIRPORT_COORDS: dict[str, tuple[float, float]] = {
    "BDJ": (-3.44,  114.76),
    "BPN": (-1.27,  116.89),
    "BTH": ( 1.12,  104.12),
    "CGK": (-6.13,  106.66),
    "DAD": (16.04,  108.20),
    "DPS": (-8.75,  115.17),
    "HAN": (21.22,  105.81),
    "HLP": (-6.27,  106.89),
    "HUI": (16.40,  107.70),
    "JHB": ( 1.64,  103.67),
    "KNO": ( 3.64,   98.87),
    "KUL": ( 2.75,  101.71),
    "LOP": (-8.76,  116.28),
    "PDG": (-0.79,  100.28),
    "PEN": ( 5.30,  100.28),
    "PGK": (-2.16,  106.14),
    "PKU": ( 0.46,  101.44),
    "PLM": (-2.90,  104.70),
    "PNK": (-0.15,  109.40),
    "PQC": (10.17,  103.99),
    "PXU": (14.00,  108.02),
    "SGN": (10.82,  106.65),
    "SIN": ( 1.35,  103.99),
    "SUB": (-7.38,  112.79),
    "SZB": ( 3.13,  101.55),
    "TJQ": (-2.74,  107.75),
    "TKG": (-5.25,  105.18),
    "UPG": (-5.08,  119.55),
    "VII": (18.74,  105.67),
    "XSP": ( 1.42,  103.87),
    "YIA": (-7.91,  110.06),
}

# ---------------------------------------------------------------------------
# Nama bandara lengkap (untuk tampilan UI)
# ---------------------------------------------------------------------------

AIRPORT_NAMES: dict[str, str] = {
    "BDJ": "Syamsuddin Noor (BDJ) — Banjarmasin",
    "BPN": "Sultan Aji Muhammad Sulaiman (BPN) — Balikpapan",
    "BTH": "Hang Nadim (BTH) — Batam",
    "CGK": "Soekarno-Hatta Terminal 3 (CGK) — Jakarta",
    "DAD": "Da Nang (DAD) — Da Nang",
    "DPS": "Ngurah Rai (DPS) — Denpasar / Bali",
    "HAN": "Noi Bai (HAN) — Hanoi",
    "HLP": "Halim Perdanakusuma (HLP) — Jakarta",
    "HUI": "Phu Bai (HUI) — Hue",
    "JHB": "Senai (JHB) — Johor Bahru",
    "KNO": "Kualanamu (KNO) — Medan",
    "KUL": "KLIA (KUL) — Kuala Lumpur",
    "LOP": "Lombok (LOP) — Lombok",
    "PDG": "Minangkabau (PDG) — Padang",
    "PEN": "Penang (PEN) — Penang",
    "PGK": "Depati Amir (PGK) — Pangkal Pinang",
    "PKU": "Sultan Syarif Kasim II (PKU) — Pekanbaru",
    "PLM": "Sultan Mahmud Badaruddin II (PLM) — Palembang",
    "PNK": "Supadio (PNK) — Pontianak",
    "PQC": "Phu Quoc (PQC) — Phu Quoc",
    "PXU": "Pleiku (PXU) — Pleiku",
    "SGN": "Tan Son Nhat (SGN) — Ho Chi Minh City",
    "SIN": "Changi (SIN) — Singapura",
    "SUB": "Juanda (SUB) — Surabaya",
    "SZB": "Subang / Sultan Abdul Aziz Shah (SZB) — Kuala Lumpur",
    "TJQ": "H.A.S. Hanandjoeddin (TJQ) — Tanjung Pandan",
    "TKG": "Radin Inten II (TKG) — Lampung",
    "UPG": "Sultan Hasanuddin (UPG) — Makassar",
    "VII": "Vinh (VII) — Vinh",
    "XSP": "Seletar (XSP) — Singapura",
    "YIA": "Yogyakarta (YIA) — Yogyakarta",
}

AIRLINE_NAMES: dict[str, str] = {
    "8B": "Transnusa (8B)",
    "9G": "Cape Air / Regional (9G)",
    "AK": "AirAsia (AK)",
    "CI": "China Airlines (CI)",
    "FY": "Firefly (FY)",
    "GA": "Garuda Indonesia (GA)",
    "ID": "Batik Air (ID)",
    "IN": "Nam Air (IN)",
    "IP": "Pelita Air (IP)",
    "IU": "Super Air Jet (IU)",
    "IW": "Wings Air (IW)",
    "JT": "Lion Air (JT)",
    "KL": "KLM (KL)",
    "MH": "Malaysia Airlines (MH)",
    "MU": "China Eastern (MU)",
    "OD": "Malindo Air (OD)",
    "QG": "Citilink (QG)",
    "QH": "Bamboo Airways (QH)",
    "QZ": "AirAsia Indonesia (QZ)",
    "SJ": "Sriwijaya Air (SJ)",
    "SQ": "Singapore Airlines (SQ)",
    "TK": "Turkish Airlines (TK)",
    "TR": "Scoot (TR)",
    "VJ": "VietJet Air (VJ)",
    "VN": "Vietnam Airlines (VN)",
    "VU": "Vietravel Airlines (VU)",
}

CLASS_LABELS: dict[str, str] = {
    "ECONOMY": "Economy",
    "PREMIUM_ECONOMY": "Premium Economy",
    "BUSINESS": "Business",
    "FIRST": "First Class",
}

# ---------------------------------------------------------------------------
# FlightPredictor
# ---------------------------------------------------------------------------


class FlightPredictor:
    """
    Kelas utama untuk prediksi harga tiket pesawat.

    v2 — Free Routing:
      - Semua kombinasi bandara_asal (17) × bandara_tujuan (30) valid,
        bukan hanya rute yang ada di data historis.
      - Untuk rute yang TIDAK ada di data:
          * jarak_km dihitung via haversine (presisi 100% vs data historis)
          * durasi_menit diestimasi proporsional berdasarkan kecepatan rata-rata
            dari sampel profil maskapai/kelas yang relevan
          * jam_tiba dihitung ulang dari jam_berangkat + durasi baru
          * Fitur lain (fasilitas, seat, dll.) diambil dari profil maskapai/kelas
      - bandara_asal & bandara_tujuan dalam encoding selalu sesuai pilihan user
    """

    # Kolom referensi yang di-drop saat dummy encoding (all zeros = reference)
    _REF_BANDARA_ASAL  = "BTH"
    _REF_BANDARA_TUJUAN = "BDJ"
    _REF_MASKAPAI      = "8B"

    # Batas selisih_hari dari data training
    _SELISIH_MIN = 1
    _SELISIH_MAX = 7

    def __init__(self):
        self._load_artifacts()
        self._build_lookup_tables()

    # ------------------------------------------------------------------
    # 1. Load Artefak
    # ------------------------------------------------------------------

    def _load_artifacts(self):
        """Load model RF, daftar kolom, dan data preprocessed."""
        self.model = joblib.load(os.path.join(_ARTIFACT_DIR, "rf_model_final.pkl"))
        self.model_columns: list[str] = joblib.load(
            os.path.join(_ARTIFACT_DIR, "model_columns.pkl")
        )
        self._feature_cols = [c for c in self.model_columns if c != "harga_idr_log"]

        self.df = pd.read_csv(os.path.join(_DATA_DIR, "data_preprocessed.csv"))

        bool_cols = ["meal", "entertainment", "usb", "power", "refundable", "reschedulable", "visa_required"]
        for col in bool_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(bool)

    # ------------------------------------------------------------------
    # 2. Build Lookup Tables
    # ------------------------------------------------------------------

    def _build_lookup_tables(self):
        """Bangun lookup tables untuk validasi dan sampling cepat."""
        df = self.df

        # Bandara valid dari model_columns
        self._valid_origins: list[str] = sorted(
            [c.replace("bandara_asal_", "") for c in self._feature_cols if c.startswith("bandara_asal_")]
            + [self._REF_BANDARA_ASAL]
        )
        self._valid_dests: list[str] = sorted(
            [c.replace("bandara_tujuan_", "") for c in self._feature_cols if c.startswith("bandara_tujuan_")]
            + [self._REF_BANDARA_TUJUAN]
        )
        self._valid_airlines: list[str] = sorted(
            [c.replace("maskapai_final_", "") for c in self._feature_cols if c.startswith("maskapai_final_")]
            + [self._REF_MASKAPAI]
        )

        # Rute yang ada di data historis
        self._valid_routes: set[tuple[str, str]] = set(zip(df["bandara_asal"], df["bandara_tujuan"]))

        # Jarak (km) dari data historis — lookup cepat untuk rute existing
        self._route_distance: dict[tuple[str, str], float] = dict(
            zip(zip(df["bandara_asal"], df["bandara_tujuan"]), df["jarak_km"])
        )

        # Kelas per maskapai
        self._airline_classes: dict[str, list[str]] = (
            df.groupby("maskapai_final")["kelas"]
            .apply(lambda x: sorted(x.unique().tolist()))
            .to_dict()
        )

    # ------------------------------------------------------------------
    # 3. Metode Query Valid Values (FREE ROUTING)
    # ------------------------------------------------------------------

    def get_valid_origins(self) -> list[str]:
        """Semua bandara asal yang valid (dari model_columns)."""
        return self._valid_origins

    def get_valid_destinations(self, origin: str | None = None) -> list[str]:
        """
        Semua bandara tujuan yang valid (dari model_columns).
        Hanya exclude origin itu sendiri agar tidak bisa CGK→CGK.
        Tidak lagi dibatasi hanya rute yang ada di data.
        """
        return sorted([d for d in self._valid_dests if d != origin])

    def get_valid_airlines(
        self,
        origin: str | None = None,
        dest: str | None = None,
        include_all: bool = True,
    ) -> list[str]:
        """
        Semua maskapai yang valid — tidak dibatasi per rute.
        include_all=True menambah opsi 'ALL' di posisi pertama.
        """
        airlines = self._valid_airlines
        return (["ALL"] + airlines) if include_all else airlines

    def get_valid_classes(self, airline: str | None = None) -> list[str]:
        """Kelas yang tersedia untuk maskapai tertentu. None/'ALL' → semua kelas."""
        order = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]
        if airline and airline != "ALL":
            classes = self._airline_classes.get(airline, order)
        else:
            classes = list({k for cls in self._airline_classes.values() for k in cls})
        return [c for c in order if c in classes]

    def is_existing_route(self, origin: str, dest: str) -> bool:
        """True jika rute ada di data historis."""
        return (origin, dest) in self._valid_routes

    # ------------------------------------------------------------------
    # 4. Hitung selisih_hari
    # ------------------------------------------------------------------

    def compute_selisih_hari(self, tanggal_terbang: date | str) -> tuple[int, bool]:
        """Hitung selisih hari dan clamp ke [1, 7]. Returns (clamped, is_out_of_range)."""
        if isinstance(tanggal_terbang, str):
            tanggal_terbang = datetime.strptime(tanggal_terbang, "%Y-%m-%d").date()
        today = date.today()
        selisih = (tanggal_terbang - today).days
        is_out = selisih < self._SELISIH_MIN or selisih > self._SELISIH_MAX
        return max(self._SELISIH_MIN, min(self._SELISIH_MAX, selisih)), is_out

    # ------------------------------------------------------------------
    # 5. Jarak & Durasi — Haversine + Estimasi
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Jarak lingkaran besar dalam km antara dua titik koordinat."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(a))

    def _calc_jarak_km(self, origin: str, dest: str) -> float:
        """
        Hitung jarak_km antara origin dan dest.
        Prioritas: lookup data historis → haversine dari koordinat.
        """
        if (origin, dest) in self._route_distance:
            return self._route_distance[(origin, dest)]
        # Haversine fallback
        if origin in AIRPORT_COORDS and dest in AIRPORT_COORDS:
            lat1, lon1 = AIRPORT_COORDS[origin]
            lat2, lon2 = AIRPORT_COORDS[dest]
            return round(self._haversine(lat1, lon1, lat2, lon2), 1)
        # Fallback terakhir: rata-rata jarak semua rute
        return float(self.df["jarak_km"].mean())

    def _estimate_durasi(
        self,
        new_jarak_km: float,
        ref_jarak_km: float | None = None,
        ref_durasi_menit: float | None = None,
    ) -> int:
        """
        Estimasi durasi penerbangan (menit) berdasarkan jarak.
        Jika ada referensi dari sampel, gunakan kecepatan proporsional.
        Kecepatan fallback: 750 km/jam (cruise speed jet pendek-menengah).
        Minimum 30 menit, tambah buffer taxi 15 menit.
        """
        if ref_jarak_km and ref_durasi_menit and ref_jarak_km > 0:
            speed_km_per_min = ref_jarak_km / ref_durasi_menit  # km/menit
            estimated = new_jarak_km / speed_km_per_min
        else:
            estimated = (new_jarak_km / 750) * 60  # 750 km/jam → menit

        # Tambah buffer taxi/ATC: 15 menit
        estimated += 15
        return max(30, round(estimated))

    # ------------------------------------------------------------------
    # 6. Time Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_jam_tiba(jam_berangkat: str, durasi_menit: int) -> str:
        """Hitung jam_tiba dari jam_berangkat + durasi (format HH:MM)."""
        try:
            bgt = datetime.strptime(jam_berangkat, "%H:%M")
            tiba = bgt + timedelta(minutes=durasi_menit)
            return tiba.strftime("%H:%M")
        except Exception:
            return "N/A"

    @staticmethod
    def _time_to_kategori(jam_str: str) -> str:
        """
        Konversi jam (HH:MM) ke kategori waktu.
        MORNING: 05-11, AFTERNOON: 12-16 (reference, tidak ada kolomnya),
        EVENING: 17-20, NIGHT: 21-04
        """
        try:
            hour = int(jam_str.split(":")[0])
            if 5 <= hour < 12:
                return "MORNING"
            elif 12 <= hour < 17:
                return "AFTERNOON"
            elif 17 <= hour < 21:
                return "EVENING"
            else:
                return "NIGHT"
        except Exception:
            return "AFTERNOON"

    # ------------------------------------------------------------------
    # 7. Sample Baris Historis — Fallback Progressif
    # ------------------------------------------------------------------

    def _sample_historical_rows(
        self,
        origin: str,
        dest: str,
        airline: str | None,
        kelas: str | None,
        is_transit: int | None,
        n: int,
        route_exists: bool = True,
    ) -> pd.DataFrame:
        """
        Ambil n baris dari data historis yang paling relevan.

        Fallback progressif (prioritaskan maskapai & kelas agar profil fasilitas cocok):
          1. Rute exact + maskapai + kelas + transit
          2. Rute exact + maskapai + kelas
          3. Maskapai + kelas (dari rute mana pun)
          4. Rute exact + kelas (dari maskapai lain)
          5. Kelas saja (dari rute/maskapai mana pun)
          6. Rute exact saja
          7. Seluruh dataset
        """
        df = self.df

        def try_filter(masks: list) -> pd.DataFrame:
            combined = masks[0].copy()
            for m in masks[1:]:
                combined &= m
            return df[combined]

        route_mask  = (df["bandara_asal"] == origin) & (df["bandara_tujuan"] == dest)
        airline_mask = (df["maskapai_final"] == airline) if (airline and airline != "ALL") else pd.Series(True, index=df.index)
        kelas_mask  = (df["kelas"] == kelas) if kelas else pd.Series(True, index=df.index)
        transit_mask = (df["is_transit"] == is_transit) if is_transit is not None else pd.Series(True, index=df.index)

        # Coba satu per satu sesuai urutan prioritas
        for masks in [
            [route_mask, airline_mask, kelas_mask, transit_mask],
            [route_mask, airline_mask, kelas_mask],
            [airline_mask, kelas_mask],
            [route_mask, kelas_mask],
            [kelas_mask],
            [route_mask],
            [pd.Series(True, index=df.index)],
        ]:
            result = try_filter(masks)
            if len(result) > 0:
                return result.sample(
                    n=min(n, len(result)),
                    replace=False,
                    random_state=None,
                )

        # Fallback akhir (untuk safety)
        return df.sample(n=min(n, len(df)), replace=False, random_state=None)

    # ------------------------------------------------------------------
    # 8. Encode Satu Baris ke Format Model
    # ------------------------------------------------------------------

    def _encode_row(
        self,
        row: pd.Series,
        selisih_hari: int,
        hari_penerbangan: int,
        override_origin: str | None = None,
        override_dest: str | None = None,
        override_jarak_km: float | None = None,
        override_durasi: int | None = None,
        override_waktu_tiba_kat: str | None = None,
        override_maskapai: str | None = None,
        override_kelas: str | None = None,
    ) -> pd.DataFrame:
        """
        Encode satu baris ke format one-hot sesuai model_columns.

        Override params digunakan untuk rute baru agar bandara, jarak,
        dan durasi sesuai pilihan user (bukan dari baris sampel).
        """
        kelas_map = {"ECONOMY": 0, "PREMIUM_ECONOMY": 1, "BUSINESS": 2, "FIRST": 3}
        wifi_map  = {"no_wifi": 0, "paid": 1, "free": 2}

        # Tentukan nilai final untuk field yang bisa di-override
        bandara_asal   = override_origin    or str(row["bandara_asal"])
        bandara_tujuan = override_dest      or str(row["bandara_tujuan"])
        jarak_km       = override_jarak_km  if override_jarak_km is not None else float(row["jarak_km"])
        durasi_menit   = override_durasi    if override_durasi   is not None else float(row["durasi_menit"])
        waktu_tiba_kat = override_waktu_tiba_kat or str(row.get("waktu_tiba_kategori", "AFTERNOON"))
        maskapai_final = override_maskapai  or str(row["maskapai_final"])
        kelas_final    = override_kelas     or str(row["kelas"])

        encoded: dict[str, float] = {}

        # --- Fitur numerik ---
        encoded["kelas"]            = float(kelas_map.get(kelas_final, 0))
        encoded["durasi_menit"]     = float(durasi_menit)
        encoded["transit"]          = float(row["transit"])
        encoded["bagasi_kg"]        = float(row["bagasi_kg"])
        encoded["cabin_baggage_kg"] = float(row["cabin_baggage_kg"])
        encoded["meal"]             = float(int(row["meal"]))
        encoded["entertainment"]    = float(int(row["entertainment"]))
        encoded["usb"]              = float(int(row["usb"]))
        encoded["power"]            = float(int(row["power"]))
        encoded["seat_pitch_inch"]  = float(row["seat_pitch_inch"]) if pd.notna(row.get("seat_pitch_inch")) else 30.0
        encoded["refundable"]       = float(int(row["refundable"]))
        encoded["reschedulable"]    = float(int(row["reschedulable"]))
        encoded["visa_required"]    = float(int(row["visa_required"]))
        encoded["wifi_status"]      = float(wifi_map.get(str(row["wifi_status"]), 0))
        encoded["selisih_hari"]     = float(selisih_hari)
        encoded["hari_penerbangan"] = float(hari_penerbangan)
        encoded["jarak_km"]         = float(jarak_km)
        encoded["is_transit"]       = float(row["is_transit"])
        encoded["jumlah_fasilitas"] = float(row["jumlah_fasilitas"])
        encoded["flight_speed_kmh"] = (float(jarak_km) / float(durasi_menit)) * 60.0 if float(durasi_menit) > 0 else 0.0

        # --- One-hot: bandara_asal (override dengan pilihan user) ---
        for col in self._feature_cols:
            if col.startswith("bandara_asal_"):
                encoded[col] = 1.0 if col == f"bandara_asal_{bandara_asal}" else 0.0

        # --- One-hot: bandara_tujuan (override dengan pilihan user) ---
        for col in self._feature_cols:
            if col.startswith("bandara_tujuan_"):
                encoded[col] = 1.0 if col == f"bandara_tujuan_{bandara_tujuan}" else 0.0

        # --- One-hot: model_pesawat ---
        for col in self._feature_cols:
            if col.startswith("model_pesawat_"):
                encoded[col] = 1.0 if col == f"model_pesawat_{row.get('model_pesawat', 'Unknown')}" else 0.0

        # --- One-hot: seat_layout ---
        for col in self._feature_cols:
            if col.startswith("seat_layout_"):
                encoded[col] = 1.0 if col == f"seat_layout_{row.get('seat_layout', 'Unknown')}" else 0.0

        # --- One-hot: seat_type ---
        for col in self._feature_cols:
            if col.startswith("seat_type_"):
                encoded[col] = 1.0 if col == f"seat_type_{row.get('seat_type', 'Unknown')}" else 0.0

        # --- One-hot: maskapai_final (8B = reference → all 0) ---
        for col in self._feature_cols:
            if col.startswith("maskapai_final_"):
                encoded[col] = 1.0 if col == f"maskapai_final_{maskapai_final}" else 0.0

        # --- One-hot: waktu_berangkat_kategori (AFTERNOON = reference) ---
        for col in self._feature_cols:
            if col.startswith("waktu_berangkat_kategori_"):
                suffix = col.replace("waktu_berangkat_kategori_", "")
                encoded[col] = 1.0 if row.get("waktu_berangkat_kategori") == suffix else 0.0

        # --- One-hot: waktu_tiba_kategori (override untuk rute baru) ---
        for col in self._feature_cols:
            if col.startswith("waktu_tiba_kategori_"):
                suffix = col.replace("waktu_tiba_kategori_", "")
                encoded[col] = 1.0 if waktu_tiba_kat == suffix else 0.0

        return pd.DataFrame([encoded])[self._feature_cols]

    # ------------------------------------------------------------------
    # 9. Prediksi Harga
    # ------------------------------------------------------------------

    def _predict_price(self, X: pd.DataFrame) -> float:
        """Prediksi harga. Model output = log(harga_idr) → exp()."""
        return float(np.exp(self.model.predict(X)[0]))

    # ------------------------------------------------------------------
    # 10. Advanced Search (Single-Shot Predictor)
    # ------------------------------------------------------------------

    def predict_advanced(
        self,
        origin: str,
        dest: str,
        tanggal_terbang: date | str,
        airline: str,
        kelas: str,
        adv_feats: dict,
    ) -> dict:
        """
        Prediksi single-shot berdasarkan fitur yang diberikan eksplisit oleh pengguna (tanpa sampling).
        """
        warnings_list: list[str] = []

        if isinstance(tanggal_terbang, str):
            tgl = datetime.strptime(tanggal_terbang, "%Y-%m-%d").date()
        else:
            tgl = tanggal_terbang

        # Selisih hari & hari penerbangan
        selisih_hari, is_out_of_range = self.compute_selisih_hari(tgl)
        if is_out_of_range:
            selisih_asli = (tgl - date.today()).days
            warnings_list.append(
                f"Tanggal terbang berada {selisih_asli} hari dari sekarang, di luar rentang data training. "
                f"Prediksi menggunakan selisih_hari={selisih_hari} sebagai estimasi terdekat."
            )

        hari_penerbangan = tgl.weekday()
        
        # Hitung jarak dan durasi otomatis
        jarak_km = self._calc_jarak_km(origin, dest)
        
        # Asumsi kecepatan rata-rata 750 km/jam jika durasi tidak di-override
        if "durasi_menit" in adv_feats:
            durasi_menit = int(adv_feats["durasi_menit"])
        else:
            flight_speed_kmh = 750.0
            durasi_menit = int((jarak_km / flight_speed_kmh) * 60)
            
            transit = adv_feats.get("transit", 0)
            if transit > 0:
                durasi_menit += 120
                
        is_transit = 1 if adv_feats.get("transit", 0) > 0 else 0
        transit = adv_feats.get("transit", 0)
            
        waktu_berangkat_kategori = adv_feats.get("waktu_berangkat_kategori", "MORNING")
        
        # Map kategori ke dummy jam_berangkat
        waktu_dummy_map = {
            "MORNING": "08:00",
            "AFTERNOON": "14:00",
            "EVENING": "19:00",
            "NIGHT": "02:00"
        }
        jam_berangkat_dummy = waktu_dummy_map.get(waktu_berangkat_kategori, "08:00")
        
        # Kalkulasi jam_tiba
        jam_tiba_dummy = self._calc_jam_tiba(jam_berangkat_dummy, durasi_menit)
        waktu_tiba_kat = self._time_to_kategori(jam_tiba_dummy)
        
        # Buat dummy row untuk di-encode
        dummy_row = {
            "bandara_asal": origin,
            "bandara_tujuan": dest,
            "maskapai_final": airline,
            "kelas": kelas,
            "jarak_km": jarak_km,
            "durasi_menit": durasi_menit,
            "transit": transit,
            "is_transit": is_transit,
            "jam_berangkat": jam_berangkat_dummy,
            "jam_tiba": jam_tiba_dummy,
            "waktu_berangkat_kategori": waktu_berangkat_kategori,
            "waktu_tiba_kategori": waktu_tiba_kat,
            "model_pesawat": adv_feats.get("model_pesawat", "Unknown"),
            "seat_layout": adv_feats.get("seat_layout", "Unknown"),
            "seat_type": adv_feats.get("seat_type", "Unknown"),
            "seat_pitch_inch": float(adv_feats.get("seat_pitch_inch", 30)),
            "bagasi_kg": float(adv_feats.get("bagasi_kg", 20)),
            "cabin_baggage_kg": float(adv_feats.get("cabin_baggage_kg", 7)),
            "wifi_status": adv_feats.get("wifi_status", "no_wifi"),
            "meal": bool(adv_feats.get("meal", False)),
            "entertainment": bool(adv_feats.get("entertainment", False)),
            "usb": bool(adv_feats.get("usb", False)),
            "power": bool(adv_feats.get("power", False)),
            "refundable": bool(adv_feats.get("refundable", False)),
            "reschedulable": bool(adv_feats.get("reschedulable", False)),
            "visa_required": bool(adv_feats.get("visa_required", False)),
        }
        
        jumlah_fasilitas = sum([dummy_row["meal"], dummy_row["entertainment"], dummy_row["usb"], dummy_row["power"]])
        if dummy_row["wifi_status"] == "free":
            jumlah_fasilitas += 1
        dummy_row["jumlah_fasilitas"] = jumlah_fasilitas
        
        row_series = pd.Series(dummy_row)
        
        X = self._encode_row(
            row_series,
            selisih_hari,
            hari_penerbangan,
            override_origin=origin,
            override_dest=dest,
            override_jarak_km=jarak_km,
            override_durasi=durasi_menit,
            override_waktu_tiba_kat=waktu_tiba_kat,
            override_maskapai=airline,
            override_kelas=kelas,
        )
        
        price = self._predict_price(X)
        ticket = self._row_to_ticket_dict(row_series, price, tgl)
        
        return {
            "tickets": [ticket],
            "warnings": warnings_list,
            "params": {
                "origin": origin,
                "dest": dest,
                "tanggal_terbang": tgl.strftime("%Y-%m-%d"),
                "airline": airline,
                "kelas": kelas,
                "is_transit": is_transit,
                "selisih_hari": selisih_hari,
                "hari_penerbangan": hari_penerbangan,
                "jarak_km": round(jarak_km, 1),
                "is_advanced": True
            },
        }

    # ------------------------------------------------------------------
    # 11. Full Search Pipeline
    # ------------------------------------------------------------------

    def search(
        self,
        origin: str,
        dest: str,
        tanggal_terbang: date | str,
        airline: str = "ALL",
        kelas: str = "ECONOMY",
        is_transit: int | None = None,
        n: int = 5,
    ) -> dict:
        """
        Pipeline pencarian lengkap — mendukung semua kombinasi rute valid.

        Untuk rute yang tidak ada di data historis:
          - jarak_km dihitung via haversine
          - durasi_menit diestimasi proporsional dari profil maskapai/kelas
          - jam_tiba dihitung ulang
          - bandara_asal / bandara_tujuan dalam encoding selalu sesuai pilihan user
        """
        warnings_list: list[str] = []

        if isinstance(tanggal_terbang, str):
            tgl = datetime.strptime(tanggal_terbang, "%Y-%m-%d").date()
        else:
            tgl = tanggal_terbang

        # Selisih hari
        selisih_hari, is_out_of_range = self.compute_selisih_hari(tgl)
        if is_out_of_range:
            selisih_asli = (tgl - date.today()).days
            warnings_list.append(
                f"Tanggal terbang {tgl.strftime('%d %b %Y')} berada "
                f"{selisih_asli} hari dari sekarang, di luar rentang data training (1–7 hari). "
                f"Prediksi menggunakan selisih_hari={selisih_hari} sebagai estimasi terdekat."
            )

        hari_penerbangan = tgl.weekday()

        # Cek apakah rute ada di data historis
        route_exists = self.is_existing_route(origin, dest)
        if not route_exists:
            warnings_list.append(
                f"Rute {origin}→{dest} tidak ada dalam data historis. "
                f"Prediksi menggunakan profil maskapai/kelas terdekat dengan "
                f"jarak yang dihitung secara geometris."
            )

        # Hitung jarak untuk rute ini
        jarak_km = self._calc_jarak_km(origin, dest)

        # Sample baris historis (lebih banyak untuk diversitas)
        sample_n = max(n * 4, 30)
        historical_rows = self._sample_historical_rows(
            origin, dest, airline, kelas, is_transit,
            n=sample_n, route_exists=route_exists,
        )

        # Encode dan prediksi tiap baris
        results = []
        for _, row in historical_rows.iterrows():
            try:
                # Hitung durasi dan jam_tiba untuk rute ini
                if route_exists:
                    # Rute existing: gunakan durasi dari data (jarak sudah cocok)
                    new_durasi  = int(row["durasi_menit"])
                    new_jam_tiba = str(row.get("jam_tiba", "N/A"))
                    new_tiba_kat = str(row.get("waktu_tiba_kategori", "AFTERNOON"))
                else:
                    # Rute baru: estimasi durasi proporsional dari kecepatan sampel
                    ref_jarak  = float(row["jarak_km"])
                    ref_durasi = float(row["durasi_menit"])
                    new_durasi = self._estimate_durasi(jarak_km, ref_jarak, ref_durasi)
                    new_jam_tiba = self._calc_jam_tiba(str(row.get("jam_berangkat", "08:00")), new_durasi)
                    new_tiba_kat = self._time_to_kategori(new_jam_tiba)

                X = self._encode_row(
                    row,
                    selisih_hari,
                    hari_penerbangan,
                    override_origin=origin,
                    override_dest=dest,
                    override_jarak_km=jarak_km,
                    override_durasi=new_durasi,
                    override_waktu_tiba_kat=new_tiba_kat,
                    override_maskapai=airline if airline != "ALL" else None,
                    override_kelas=kelas if kelas else None,
                )
                price = self._predict_price(X)

                # Buat copy row dengan nilai yang sudah di-override
                display_row = row.copy()
                display_row["bandara_asal"]          = origin
                display_row["bandara_tujuan"]         = dest
                display_row["jarak_km"]               = jarak_km
                display_row["durasi_menit"]           = new_durasi
                display_row["jam_tiba"]               = new_jam_tiba
                display_row["waktu_tiba_kategori"]    = new_tiba_kat
                if airline != "ALL":
                    display_row["maskapai_final"]     = airline
                if kelas:
                    display_row["kelas"]              = kelas
                if not route_exists:
                    display_row["is_transit"] = 0
                    display_row["transit"]    = 0
                    display_row["bandara_transit"] = ""

                ticket = self._row_to_ticket_dict(display_row, price, tgl)
                results.append(ticket)

            except Exception:
                continue

        # Deduplicate: (maskapai, kelas, model_pesawat, is_transit, jam_berangkat)
        seen: set = set()
        unique_results: list = []
        for t in results:
            key = (t["maskapai"], t["kelas"], t["model_pesawat"], t["is_transit"], t["jam_berangkat"])
            if key not in seen:
                seen.add(key)
                unique_results.append(t)

        # Urutkan termurah
        unique_results.sort(key=lambda x: x["harga_idr"])
        tickets = unique_results[:n]

        if not tickets:
            warnings_list.append("Tidak ada hasil yang ditemukan untuk parameter pencarian ini.")

        return {
            "tickets": tickets,
            "warnings": warnings_list,
            "params": {
                "origin": origin,
                "dest": dest,
                "tanggal_terbang": tgl.strftime("%Y-%m-%d"),
                "airline": airline,
                "kelas": kelas,
                "is_transit": is_transit,
                "selisih_hari": selisih_hari,
                "hari_penerbangan": hari_penerbangan,
                "jarak_km": round(jarak_km, 1),
                "route_exists": route_exists,
                "n_requested": n,
                "n_found": len(tickets),
            },
        }

    # ------------------------------------------------------------------
    # 11. Helper: Row → Ticket Dict (untuk tampilan)
    # ------------------------------------------------------------------

    def _row_to_ticket_dict(self, row: pd.Series, harga_idr: float, tgl_terbang: date) -> dict:
        """Konversi baris (dengan override) + harga prediksi → dict tiket."""
        jam_berangkat = str(row.get("jam_berangkat", "N/A"))
        jam_tiba      = str(row.get("jam_tiba", "N/A"))
        durasi        = int(row.get("durasi_menit", 0))

        tiba_besok = False
        try:
            bgt  = datetime.strptime(jam_berangkat, "%H:%M")
            tiba = datetime.strptime(jam_tiba, "%H:%M")
            if tiba < bgt and durasi > 0:
                tiba_besok = True
        except Exception:
            pass

        maskapai_code      = str(row.get("maskapai_final", ""))
        bandara_transit_raw = str(row.get("bandara_transit", ""))
        jarak_km_val = float(row.get("jarak_km", 0))
        flight_speed = round((jarak_km_val / durasi) * 60.0) if durasi > 0 else 0

        return {
            "maskapai":             maskapai_code,
            "maskapai_nama":        AIRLINE_NAMES.get(maskapai_code, maskapai_code),
            "kelas":                str(row.get("kelas", "")),
            "kelas_label":          CLASS_LABELS.get(str(row.get("kelas", "")), str(row.get("kelas", ""))),
            "bandara_asal":         str(row.get("bandara_asal", "")),
            "bandara_tujuan":       str(row.get("bandara_tujuan", "")),
            "bandara_asal_nama":    AIRPORT_NAMES.get(str(row.get("bandara_asal", "")), str(row.get("bandara_asal", ""))),
            "bandara_tujuan_nama":  AIRPORT_NAMES.get(str(row.get("bandara_tujuan", "")), str(row.get("bandara_tujuan", ""))),
            "tanggal_terbang":      tgl_terbang.strftime("%Y-%m-%d"),
            "jam_berangkat":        jam_berangkat,
            "jam_tiba":             jam_tiba,
            "tiba_besok":           tiba_besok,
            "durasi_menit":         durasi,
            "transit":              int(row.get("transit", 0)),
            "is_transit":           int(row.get("is_transit", 0)),
            "bandara_transit":      bandara_transit_raw if bandara_transit_raw not in ("nan", "None", "") else "-",
            "model_pesawat":        str(row.get("model_pesawat", "Unknown")),
            "seat_layout":          str(row.get("seat_layout", "Unknown")),
            "seat_pitch_inch":      float(row.get("seat_pitch_inch", 0)) if pd.notna(row.get("seat_pitch_inch")) else None,
            "seat_type":            str(row.get("seat_type", "Unknown")),
            "bagasi_kg":            int(row.get("bagasi_kg", 0)),
            "cabin_baggage_kg":     int(row.get("cabin_baggage_kg", 0)),
            "meal":                 bool(row.get("meal", False)),
            "entertainment":        bool(row.get("entertainment", False)),
            "usb":                  bool(row.get("usb", False)),
            "power":                bool(row.get("power", False)),
            "wifi_status":          str(row.get("wifi_status", "no_wifi")),
            "jumlah_fasilitas":     int(row.get("jumlah_fasilitas", 0)),
            "refundable":           bool(row.get("refundable", False)),
            "reschedulable":        bool(row.get("reschedulable", False)),
            "visa_required":        bool(row.get("visa_required", False)),
            "waktu_berangkat_kategori": str(row.get("waktu_berangkat_kategori", "")),
            "waktu_tiba_kategori":  str(row.get("waktu_tiba_kategori", "")),
            "flight_speed_kmh":     flight_speed,
            "harga_idr":            harga_idr,
            "harga_idr_formatted":  f"Rp {harga_idr:,.0f}".replace(",", "."),
            "is_reference_airline": maskapai_code == self._REF_MASKAPAI,
        }

    # ------------------------------------------------------------------
    # 12. Utility
    # ------------------------------------------------------------------

    @staticmethod
    def format_durasi(durasi_menit: int) -> str:
        jam   = durasi_menit // 60
        menit = durasi_menit % 60
        if jam > 0 and menit > 0:
            return f"{jam}j {menit}m"
        elif jam > 0:
            return f"{jam}j"
        return f"{menit}m"
