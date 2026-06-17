"""
cli_demo.py — CLI Interaktif untuk Prediksi Harga Tiket Pesawat
Showcase model Random Forest yang sudah dilatih.

Penggunaan:
    python cli_demo.py
"""

import os
import sys
from datetime import date, datetime

# Pastikan script folder ada di path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from tabulate import tabulate
except ImportError:
    print("⚠  Paket 'tabulate' belum terinstall. Install dengan: pip install tabulate")
    sys.exit(1)

from backend import FlightPredictor, AIRPORT_NAMES, AIRLINE_NAMES, CLASS_LABELS

# ---------------------------------------------------------------------------
# Konstanta & Helper UI
# ---------------------------------------------------------------------------

SEPARATOR = "─" * 72
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
DIM = "\033[2m"
RESET = "\033[0m"

WIFI_LABEL = {"no_wifi": "✗ No WiFi", "paid": "💲 Berbayar", "free": "✓ Gratis"}
YES = f"{GREEN}✓{RESET}"
NO = f"{DIM}✗{RESET}"


def cls():
    os.system("clear" if os.name != "nt" else "cls")


def header():
    print(f"\n{CYAN}{BOLD}{'═'*72}{RESET}")
    print(f"{CYAN}{BOLD}  ✈  PREDIKSI HARGA TIKET PESAWAT  —  Powered by Random Forest{RESET}")
    print(f"{CYAN}{BOLD}{'═'*72}{RESET}\n")


def prompt(text: str, default: str | None = None) -> str:
    """Input prompt dengan default value."""
    if default:
        suffix = f" [{default}]"
    else:
        suffix = ""
    val = input(f"  {BOLD}{text}{RESET}{suffix}: ").strip()
    if not val and default:
        return default
    return val


def prompt_int(text: str, min_val: int, max_val: int, default: int) -> int:
    """Input angka integer dengan validasi range."""
    while True:
        raw = prompt(text, str(default))
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  {RED}Masukkan angka antara {min_val} dan {max_val}.{RESET}")
        except ValueError:
            print(f"  {RED}Harus berupa angka.{RESET}")


def choose_from_list(title: str, options: list[str], labels: dict[str, str] | None = None, allow_all: bool = False) -> str:
    """Tampilkan menu pilihan dan minta user memilih."""
    print(f"\n  {BOLD}{title}{RESET}")
    start = 0
    display_options = []

    if allow_all:
        display_options = ["ALL"] + options
    else:
        display_options = options

    for i, opt in enumerate(display_options, 1):
        label = ""
        if labels and opt in labels:
            label = f"  {DIM}— {labels[opt]}{RESET}"
        print(f"    {CYAN}[{i:>2}]{RESET} {opt}{label}")

    while True:
        raw = prompt(f"Pilih (1–{len(display_options)})")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(display_options):
                return display_options[idx]
            print(f"  {RED}Pilih antara 1 dan {len(display_options)}.{RESET}")
        except ValueError:
            print(f"  {RED}Harus berupa angka.{RESET}")


def prompt_date(text: str) -> date | None:
    """Input tanggal format YYYY-MM-DD atau DD-MM-YYYY. Kosong = None."""
    print(f"  {DIM}Format: YYYY-MM-DD atau DD-MM-YYYY. Kosong untuk skip.{RESET}")
    while True:
        raw = prompt(text)
        if not raw:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        print(f"  {RED}Format tanggal tidak dikenali. Coba lagi.{RESET}")


def print_warning(msg: str):
    print(f"\n  {YELLOW}⚠  {msg}{RESET}")


def print_info(msg: str):
    print(f"  {DIM}ℹ  {msg}{RESET}")


# ---------------------------------------------------------------------------
# Tampilkan Hasil Tiket
# ---------------------------------------------------------------------------

def format_fasilitas(ticket: dict) -> str:
    parts = []
    if ticket["meal"]:
        parts.append("🍽 Meal")
    if ticket["entertainment"]:
        parts.append("🎬 Entertainment")
    if ticket["usb"]:
        parts.append("🔌 USB")
    if ticket["power"]:
        parts.append("⚡ Power")
    wifi = WIFI_LABEL.get(ticket["wifi_status"], "")
    if wifi:
        parts.append(f"📶 WiFi: {ticket['wifi_status']}")
    return "  ".join(parts) if parts else "Tidak ada fasilitas tambahan"


def print_ticket_card(idx: int, ticket: dict):
    """Cetak kartu tiket ke terminal."""
    print(f"\n  {CYAN}{'─'*68}{RESET}")
    
    # Header kartu
    rank_label = f"{GREEN}#{idx}{RESET}" if idx == 1 else f"#{idx}"
    maskapai_label = f"{BOLD}{ticket['maskapai_nama']}{RESET}"
    kelas_label = f"{ticket['kelas_label']}"
    print(f"  {rank_label}  {maskapai_label}  {DIM}|{RESET}  {kelas_label}")

    # Rute & Waktu
    tiba_besok_label = f" {YELLOW}(+1){RESET}" if ticket["tiba_besok"] else ""
    durasi_str = FlightPredictor.format_durasi(ticket["durasi_menit"])
    transit_str = (
        f"{YELLOW}Transit {ticket['transit']}x ({ticket['bandara_transit']}){RESET}"
        if ticket["is_transit"] else f"{GREEN}Langsung{RESET}"
    )
    print(f"\n    {BOLD}{ticket['jam_berangkat']}{RESET}  ─────────────  {BOLD}{ticket['jam_tiba']}{RESET}{tiba_besok_label}")
    print(f"    {ticket['bandara_asal']}   {DIM}({durasi_str}){RESET}   {ticket['bandara_tujuan']}")
    print(f"    {transit_str}")

    # Pesawat & Kursi
    pitch_str = f"{ticket['seat_pitch_inch']:.0f} inch" if ticket["seat_pitch_inch"] else "N/A"
    print(f"\n    🛩  {ticket['model_pesawat']}  {DIM}|{RESET}  Layout: {ticket['seat_layout']}  {DIM}|{RESET}  Pitch: {pitch_str}")
    print(f"    💺  {ticket['seat_type'].replace('_', ' ').title()}")

    # Bagasi & Fasilitas
    print(f"\n    🧳  Bagasi: {ticket['bagasi_kg']} kg  {DIM}|{RESET}  Kabin: {ticket['cabin_baggage_kg']} kg")
    print(f"    {format_fasilitas(ticket)}")

    # Status
    ref_label = ""
    if ticket["is_transit"] and ticket["is_reference_airline"]:
        ref_label = f"  {DIM}[estimasi baseline]{RESET}"
    elif ticket["is_reference_airline"]:
        ref_label = f"  {DIM}[estimasi baseline]{RESET}"

    status_parts = []
    status_parts.append(f"{'✓ Refundable' if ticket['refundable'] else '✗ Non-refundable'}")
    status_parts.append(f"{'✓ Reschedulable' if ticket['reschedulable'] else '✗ Non-reschedulable'}")
    if ticket["visa_required"]:
        status_parts.append(f"{YELLOW}⚠ Visa Required{RESET}")
    print(f"\n    {'  |  '.join(status_parts)}{ref_label}")

    # Harga
    print(f"\n    {BOLD}{GREEN}💰  {ticket['harga_idr_formatted']}{RESET}")


def print_results(result: dict, label: str = "Berangkat"):
    """Tampilkan semua tiket dari hasil search."""
    tickets = result["tickets"]
    params = result["params"]

    print(f"\n{SEPARATOR}")
    print(f"  {BOLD}HASIL PENCARIAN  —  {label.upper()}{RESET}")
    print(f"  {params['origin']} → {params['dest']}  {DIM}|{RESET}  "
          f"{params['tanggal_terbang']}  {DIM}|{RESET}  "
          f"{params['kelas']}  {DIM}|{RESET}  "
          f"Maskapai: {params['airline']}")
    print(f"  Ditemukan: {params['n_found']} tiket")

    for w in result["warnings"]:
        print_warning(w)

    if not tickets:
        print(f"\n  {RED}Tidak ada hasil ditemukan.{RESET}")
        return

    for i, ticket in enumerate(tickets, 1):
        print_ticket_card(i, ticket)

    print(f"\n  {CYAN}{'─'*68}{RESET}")
    print(f"\n  {DIM}* Harga adalah estimasi prediksi model, bukan harga resmi maskapai.{RESET}")
    print(f"  {DIM}* Data referensi: Traveloka (Mei 2026){RESET}")


# ---------------------------------------------------------------------------
# Ringkasan Tabel (opsional, lebih ringkas)
# ---------------------------------------------------------------------------

def print_results_table(result: dict, label: str = "Berangkat"):
    """Tampilkan hasil dalam format tabel ASCII ringkas."""
    tickets = result["tickets"]
    if not tickets:
        return

    rows = []
    for i, t in enumerate(tickets, 1):
        tiba_label = t["jam_tiba"] + (" (+1)" if t["tiba_besok"] else "")
        transit_label = f"Transit {t['transit']}x" if t["is_transit"] else "Langsung"
        rows.append([
            f"#{i}",
            t["maskapai"],
            t["kelas_label"][:8],
            t["jam_berangkat"],
            tiba_label,
            FlightPredictor.format_durasi(t["durasi_menit"]),
            transit_label,
            t["model_pesawat"][:14],
            t["harga_idr_formatted"],
        ])

    headers = ["#", "Mskapai", "Kelas", "Brgkt", "Tiba", "Durasi", "Transit", "Pesawat", "Harga (IDR)"]
    print(f"\n  {BOLD}— {label.upper()} ({result['params']['origin']} → {result['params']['dest']}) —{RESET}")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))


# ---------------------------------------------------------------------------
# Main CLI Loop
# ---------------------------------------------------------------------------

def run_cli():
    predictor = FlightPredictor()

    cls()
    header()
    print(f"  Selamat datang! Sistem ini mensimulasikan prediksi harga tiket pesawat")
    print(f"  menggunakan model Machine Learning (Random Forest) yang dilatih dari")
    print(f"  data tiket Traveloka periode Mei 2026.\n")

    while True:
        print(f"\n{SEPARATOR}")
        print(f"  {BOLD}PENCARIAN TIKET{RESET}")
        print(SEPARATOR)

        # --- 1. Bandara Asal ---
        origins = predictor.get_valid_origins()
        origin = choose_from_list(
            "Pilih Bandara Asal:",
            origins,
            labels={k: AIRPORT_NAMES.get(k, k) for k in origins},
        )

        # --- 2. Bandara Tujuan ---
        dests = predictor.get_valid_destinations(origin)
        if not dests:
            print_warning(f"Tidak ada rute dari {origin} yang tersedia di data.")
            continue
        dest = choose_from_list(
            "Pilih Bandara Tujuan:",
            dests,
            labels={k: AIRPORT_NAMES.get(k, k) for k in dests},
        )

        # --- 3. Tanggal Berangkat ---
        print(f"\n  {BOLD}Tanggal Berangkat{RESET}")
        tgl_berangkat = prompt_date("Tanggal berangkat")
        if not tgl_berangkat:
            print_warning("Tanggal berangkat wajib diisi.")
            continue
        if tgl_berangkat < date.today():
            print_warning("Tanggal berangkat tidak boleh di masa lalu.")
            continue

        # --- 4. Tanggal Pulang (opsional) ---
        print(f"\n  {BOLD}Tanggal Pulang (opsional — kosong untuk one-way){RESET}")
        tgl_pulang = prompt_date("Tanggal pulang")
        if tgl_pulang and tgl_pulang <= tgl_berangkat:
            print_warning("Tanggal pulang harus setelah tanggal berangkat. Diabaikan.")
            tgl_pulang = None

        # --- 5. Maskapai ---
        airlines = predictor.get_valid_airlines(origin, dest, include_all=True)
        airline = choose_from_list(
            "Pilih Maskapai:",
            airlines,
            labels={k: AIRLINE_NAMES.get(k, k) for k in airlines if k != "ALL"},
        )

        # --- 6. Kelas ---
        classes = predictor.get_valid_classes(airline if airline != "ALL" else None)
        if not classes:
            classes = ["ECONOMY"]
        kelas = choose_from_list(
            "Pilih Kelas:",
            classes,
            labels=CLASS_LABELS,
        )

        # --- 7. Transit ---
        print(f"\n  {BOLD}Preferensi Transit{RESET}")
        print(f"    {CYAN}[1]{RESET} Semua (langsung & transit)")
        print(f"    {CYAN}[2]{RESET} Langsung saja")
        print(f"    {CYAN}[3]{RESET} Transit saja")
        transit_input = prompt("Pilih (1–3)", "1")
        is_transit_map = {"1": None, "2": 0, "3": 1}
        is_transit = is_transit_map.get(transit_input, None)

        # --- 8. Jumlah Hasil ---
        n = prompt_int("Jumlah tiket yang ingin ditampilkan", 1, 10, 5)

        # --- 9. Mode Tampilan ---
        print(f"\n  {BOLD}Mode Tampilan{RESET}")
        print(f"    {CYAN}[1]{RESET} Detail (kartu tiket)")
        print(f"    {CYAN}[2]{RESET} Ringkas (tabel)")
        view_mode = prompt("Pilih (1/2)", "1")

        print(f"\n{SEPARATOR}")
        print(f"  {DIM}⟳  Memproses pencarian...{RESET}")

        # --- Prediksi Berangkat ---
        try:
            result_go = predictor.search(
                origin=origin,
                dest=dest,
                tanggal_terbang=tgl_berangkat,
                airline=airline,
                kelas=kelas,
                is_transit=is_transit,
                n=n,
            )
        except ValueError as e:
            print_warning(str(e))
            continue

        if view_mode == "2":
            print_results_table(result_go, label="Berangkat")
        else:
            print_results(result_go, label="Berangkat")

        # --- Prediksi Pulang (jika ada) ---
        if tgl_pulang:
            try:
                result_back = predictor.search(
                    origin=dest,
                    dest=origin,
                    tanggal_terbang=tgl_pulang,
                    airline=airline,
                    kelas=kelas,
                    is_transit=is_transit,
                    n=n,
                )
                if view_mode == "2":
                    print_results_table(result_back, label="Pulang")
                else:
                    print_results(result_back, label="Pulang")
            except ValueError as e:
                print_warning(f"Tiket pulang: {e}")

        # --- Lanjut atau keluar ---
        print(f"\n{SEPARATOR}")
        lanjut = prompt("Cari lagi? (y/n)", "y").lower()
        if lanjut != "y":
            print(f"\n  {CYAN}Terima kasih! Sampai jumpa. ✈{RESET}\n")
            break
        cls()
        header()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_cli()
