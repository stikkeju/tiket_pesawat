import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from curl_cffi import requests as cf_requests
import uuid
import time
import json
import pandas as pd
import os
import shutil
from datetime import datetime, timedelta

# ── 1. AMBIL SESSION DARI SELENIUM ────────────────────────────────────────────

def get_session(asal="CGK", tujuan="DPS",
                seat_class="ECONOMY", num_adults=1, num_children=0, num_infants=0):
    """Buka Traveloka sekali via Selenium untuk ambil cookies yang valid."""
    print("Membuka Traveloka untuk ambil session...")

    options = uc.ChromeOptions()
    options.binary_location = "/usr/bin/chromium-browser"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options)

    tanggal = (datetime.today() + timedelta(days=1)).strftime("%-d-%-m-%Y")
    ps      = f"{num_adults}.{num_children}.{num_infants}"
    url     = f"https://www.traveloka.com/id-id/flight/fullsearch?ap={asal}.{tujuan}&dt={tanggal}.NA&ps={ps}&sc={seat_class}"
    driver.get(url)

    print("Menunggu halaman load & cookies terbentuk...")
    time.sleep(30)

    print(f"Title halaman: {driver.title}")
    print(f"URL saat ini: {driver.current_url}")

    cookies           = {c["name"]: c["value"] for c in driver.get_cookies()}
    client_session_id = cookies.get("clientSessionId", "")
    mcc_id            = cookies.get("tv_mcc_id", "")

    driver.quit()
    print(f"Session berhasil! clientSessionId: {client_session_id[:20]}...")

    print(f"Jumlah cookies: {len(cookies)}")
    print(f"aws-waf-token ada: {'aws-waf-token' in cookies}")
    print(f"clientSessionId ada: {'clientSessionId' in cookies}")
    return cookies, client_session_id, mcc_id


# ── 2. BUILD HEADERS & PAYLOAD ─────────────────────────────────────────────────

def build_headers(cookies, client_session_id, mcc_id):
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    return {
        "Content-Type"       : "application/json",
        "User-Agent"         : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Origin"             : "https://www.traveloka.com",
        "Referer"            : "https://www.traveloka.com/id-id/flight/fullsearch",
        "cookie"             : cookie_str,
        "tv-clientsessionid" : client_session_id,
        "tv-country"         : "ID",
        "tv-currency"        : "IDR",
        "tv-language"        : "id_ID",
        "tv-mcc-id"          : mcc_id,
        "x-client-interface" : "desktop",
        "x-domain"           : "flight",
        "x-route-prefix"     : "id-id",
        "t-a-v"              : "262192",
    }

def build_payload(asal, tujuan, tanggal, search_id,
                  seat_class="ECONOMY", num_adults=1, num_children=0, num_infants=0):
    return {
        "fields": [],
        "data": {
            "tripType"           : "ONE_WAY",
            "seatPublishedClass" : seat_class,
            "journeys"           : [{"originCode": asal, "destinationCode": tujuan, "departureDate": tanggal}],
            "journeyIndex"       : 0,
            "selectedFlights"    : [],
            "numSeats"           : {"numAdults": num_adults, "numChildren": num_children, "numInfants": num_infants},
            "searchId"           : search_id,
            "currency"           : "IDR",
            "additionalData"     : {
                "utmId": None, "utmSource": None, "utmIdMarketing": None,
                "pageName": "SEARCH_RESULT", "searchSource": "ONE_WAY",
                "visitId": str(uuid.uuid4()),
                "usePromoFinder": True, "useDateFlow": False,
                "isBreakSmartCombo": False, "prefetchFlag": False,
                "isBaggageFilterEnabled": False
            },
            "filter"                      : {"standAlone": True},
            "inventoryPricingDisplayType" : "INDEPENDENT",
            "sharedFlights"               : [],
            "trackingMap"                 : {}
        },
        "clientInterface": "desktop"
    }


# ── 3. CHECKPOINT SYSTEM ───────────────────────────────────────────────────────

CHECKPOINT_FILE = "../data/raw/checkpoint.json"

def save_checkpoint(rute_idx, hari_idx, kelas_idx, output_file):
    """Simpan posisi scraping terakhir ke file JSON."""
    os.makedirs("data/raw", exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({
            "rute_idx"    : rute_idx,
            "hari_idx"    : hari_idx,
            "kelas_idx"   : kelas_idx,
            "output_file" : output_file,
            "saved_at"    : datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        }, f, indent=2)

def load_checkpoint():
    """Load checkpoint terakhir. Return None kalau tidak ada."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            cp = json.load(f)
        print(f"Checkpoint ditemukan!")
        print(f"  Terakhir disimpan : {cp['saved_at']}")
        print(f"  Melanjutkan dari  : rute={cp['rute_idx']}, hari={cp['hari_idx']}, kelas={cp['kelas_idx']}")
        print(f"  Output file       : {cp['output_file']}")
        return cp
    return None

def clear_checkpoint():
    """Hapus checkpoint setelah run selesai."""
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("Checkpoint dihapus — run selesai.")


# ── 4. HELPER PARSING ──────────────────────────────────────────────────────────

def parse_time(t):
    """Ubah {'hour': '10', 'minute': '30'} → '10:30'"""
    if not t or not isinstance(t, dict):
        return "N/A"
    h = t.get("hour", "0").zfill(2)
    m = t.get("minute", "0").zfill(2)
    return f"{h}:{m}"

def safe_get(d, *keys, default="N/A"):
    """Ambil nilai nested dict dengan aman."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d if d is not None else default


# ── 5. EKSTRAK SEMUA FITUR ────────────────────────────────────────────────────

def extract_tickets(search_results, asal, tujuan, tanggal, seat_class):
    hasil = []
    for ticket in search_results:
        try:
            # Guard: skip tiket yang tidak punya connectingFlightRoutes
            routes = ticket.get("connectingFlightRoutes")
            if not routes or not routes[0].get("segments"):
                continue

            fare             = ticket["fare"]["display"]["currencyValue"]
            harga_idr        = int(fare["amount"])
            fm               = ticket["flightMetadata"]
            total_stop       = fm["totalNumStop"]
            durasi_total     = fm["tripDuration"]
            maskapai_ids     = fm["airlineIds"]
            transit_airports = fm.get("transitAirportCodes", [])
            is_refundable    = fm["isRefundable"]
            is_reschedulable = fm["isReschedulable"]
            seat_class_label = fm.get("seatClassLabel") or seat_class

            segments  = routes[0]["segments"]
            seg_first = segments[0]
            seg_last  = segments[-1]

            flight_number     = seg_first.get("flightNumber", "N/A")
            operating_airline = seg_first.get("operatingAirlineCode", "N/A")
            bandara_asal      = seg_first.get("departureAirport") or asal
            bandara_tujuan    = seg_last.get("arrivalAirport") or tujuan

            jam_berangkat      = parse_time(seg_first.get("departureTime"))
            jam_tiba           = parse_time(seg_last.get("arrivalTime"))
            tgl_tiba           = seg_last.get("arrivalDate", tanggal)
            terminal_berangkat = seg_first.get("departureTerminalName") or "N/A"
            terminal_tiba      = seg_last.get("arrivalTerminalName") or "N/A"

            fac          = seg_first.get("facilities") or {}
            bagasi       = fac.get("baggage") or {}
            bagasi_kg    = safe_get(bagasi, "weight", default=0)
            bagasi_unit  = safe_get(bagasi, "unitOfMeasure", default="N/A")
            aircraft_info = seg_first.get("aircraftInformation") or {}
            cabin_baggage = aircraft_info.get("cabinBaggage") or {}
            cabin_bg_kg   = safe_get(cabin_baggage, "weight", default=0)

            wifi_avail    = safe_get(fac, "wifi", "available", default=False)
            wifi_cost     = safe_get(fac, "wifi", "cost", default="N/A")
            meal_avail    = safe_get(fac, "freeMeal", "available", default=False)
            entertainment = safe_get(fac, "entertainment", "available", default=False)
            usb_avail     = safe_get(fac, "usbAndPower", "usb", default=False)
            power_avail   = safe_get(fac, "usbAndPower", "power", default=False)

            aircraft      = aircraft_info.get("aircraft") or {}
            model_pesawat = safe_get(aircraft, "model", default="N/A")
            seat_info     = aircraft.get("seatInformation") or {}
            seat_layout   = safe_get(seat_info, "layout", default="N/A")
            seat_pitch    = safe_get(seat_info, "pitch", default="N/A")
            seat_type     = safe_get(seat_info, "type", default="N/A")
            visa_required = seg_first.get("visaRequired", False)

            hasil.append({
                "tanggal_scraping"   : datetime.today().strftime("%Y-%m-%d %H:%M"),
                "area_asal"          : asal,
                "area_tujuan"        : tujuan,
                "bandara_asal"       : bandara_asal,
                "bandara_tujuan"     : bandara_tujuan,
                "tanggal_terbang"    : tanggal,
                "kelas"              : seat_class_label,
                "maskapai"           : ", ".join(maskapai_ids),
                "maskapai_operasi"   : operating_airline,
                "nomor_penerbangan"  : flight_number,
                "jam_berangkat"      : jam_berangkat,
                "jam_tiba"           : jam_tiba,
                "tgl_tiba"           : tgl_tiba,
                "terminal_berangkat" : terminal_berangkat,
                "terminal_tiba"      : terminal_tiba,
                "durasi_menit"       : durasi_total,
                "transit"            : total_stop,
                "bandara_transit"    : ", ".join(transit_airports) if transit_airports else "Direct",
                "bagasi_kg"          : bagasi_kg,
                "bagasi_unit"        : bagasi_unit,
                "cabin_baggage_kg"   : cabin_bg_kg,
                "wifi"               : wifi_avail,
                "wifi_cost"          : wifi_cost,
                "meal"               : meal_avail,
                "entertainment"      : entertainment,
                "usb"                : usb_avail,
                "power"              : power_avail,
                "model_pesawat"      : model_pesawat,
                "seat_layout"        : seat_layout,
                "seat_pitch_inch"    : seat_pitch,
                "seat_type"          : seat_type,
                "harga_idr"          : harga_idr,
                "refundable"         : is_refundable,
                "reschedulable"      : is_reschedulable,
                "visa_required"      : visa_required,
            })

        except Exception as e:
            print(f"  Skip tiket: {e}")
    return hasil


# ── 6. SCRAPE SATU RUTE ────────────────────────────────────────────────────────

def scrape_rute(asal, tujuan, tanggal, headers_container,
                seat_class="ECONOMY", num_adults=1, num_children=0, num_infants=0):
    search_id = str(uuid.uuid4())
    payload   = build_payload(asal, tujuan, tanggal, search_id,
                              seat_class, num_adults, num_children, num_infants)

    print(f"  Scraping {asal}→{tujuan} | {tanggal} | {seat_class}...")

    # Initial request dengan auto-refresh session jika 405
    for attempt in range(1, 4):
        try:
            resp = cf_requests.post(
                "https://www.traveloka.com/api/v2/flight/search/initial",
                json=payload,
                headers=headers_container[0],
                timeout=15,
                impersonate="chrome"
            )
            if resp.status_code in [200, 202]:
                break
            elif resp.status_code == 403:
                print(f"  403 response body: {resp.text[:500]}")
                return []
            elif resp.status_code == 405:
                print(f"  Session expired (405), refresh... (percobaan {attempt})")
                cookies, csid, mcc = get_session(
                    asal, tujuan, seat_class, num_adults, num_children, num_infants
                )
                headers_container[0] = build_headers(cookies, csid, mcc)
                time.sleep(3)
            else:
                print(f"  Initial gagal: HTTP {resp.status_code}")
                return []
        except Exception as e:
            print(f"  Initial error: {e}")
            return []
    else:
        print(f"  Gagal setelah 3 percobaan, skip.")
        return []

    # Poll sampai searchCompleted == True
    all_results = []
    for poll_num in range(1, 25):
        time.sleep(1.5)
        try:
            resp = cf_requests.post(
                "https://www.traveloka.com/api/v2/flight/search/poll",
                json=payload,
                headers=headers_container[0],
                timeout=15,
                impersonate="chrome"
            )
            data    = resp.json()
            meta    = data["data"]["meta"]
            results = data["data"]["searchResults"]

            print(f"  Poll {poll_num}: {len(results)} tiket | selesai: {meta['searchCompleted']}")
            all_results = results

            if meta["searchCompleted"]:
                # Deteksi soft block — expiryTimeStamp null = soft block
                if len(results) == 0 and meta.get("expiryTimeStamp") is None:
                    print(f"  SOFT BLOCK terdeteksi (expiryTimeStamp=null)")
                    return None  # None = sinyal soft block ke scrape_semua
                break

        except Exception as e:
            print(f"  Poll {poll_num} error: {e}")
            break

    tickets = extract_tickets(all_results, asal, tujuan, tanggal, seat_class)
    print(f"  → {len(tickets)} tiket berhasil diekstrak")
    return tickets


# ── 7. MAIN ────────────────────────────────────────────────────────────────────

ALL_SEAT_CLASSES = ["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]

def scrape_semua(rute_list, hari_kedepan=7,
                 seat_classes=ALL_SEAT_CLASSES,
                 num_adults=1, num_children=0, num_infants=0):

    # Cek apakah ada checkpoint dari run sebelumnya
    cp            = load_checkpoint()
    start_rute    = cp["rute_idx"]  if cp else 0
    start_hari    = cp["hari_idx"]  if cp else 0
    start_kelas   = cp["kelas_idx"] if cp else 0

    # Tentukan output file — lanjutkan file yang sama kalau ada checkpoint
    os.makedirs("data/raw", exist_ok=True)
    if cp and os.path.exists(cp["output_file"]):
        output_file    = cp["output_file"]
        header_written = True   # file sudah ada, jangan tulis header lagi
        print(f"Melanjutkan ke file: {output_file}")
    else:
        output_file    = f"../data/raw/tiket_lengkap_{datetime.today().strftime('%Y%m%d_%H%M')}.csv"
        header_written = False
        print(f"File output baru: {output_file}")

    # Ambil session awal
    asal_ref, tujuan_ref = rute_list[start_rute]
    cookies, csid, mcc   = get_session(
        asal_ref, tujuan_ref, seat_classes[0], num_adults, num_children, num_infants
    )
    headers_container = [build_headers(cookies, csid, mcc)]

    total_request = len(rute_list) * hari_kedepan * len(seat_classes)
    req_ke        = start_rute * hari_kedepan * len(seat_classes) + \
                    start_hari * len(seat_classes) + start_kelas
    waktu_mulai   = time.time()

    for rute_idx, (asal, tujuan) in enumerate(rute_list):
        if rute_idx < start_rute:
            continue  # skip rute yang sudah selesai

        for hari_idx in range(hari_kedepan):
            if rute_idx == start_rute and hari_idx < start_hari:
                continue  # skip hari yang sudah selesai

            tanggal = (datetime.today() + timedelta(days=hari_idx + 1)).strftime("%Y-%m-%d")

            for kelas_idx, seat_class in enumerate(seat_classes):
                # Skip kombinasi yang sudah selesai sebelum terhenti
                if rute_idx == start_rute and hari_idx == start_hari and kelas_idx < start_kelas:
                    continue

                req_ke += 1

                # Estimasi waktu tersisa
                elapsed   = time.time() - waktu_mulai
                per_req   = elapsed / req_ke if req_ke > 0 else 15
                sisa_req  = total_request - req_ke
                eta_menit = int(sisa_req * per_req / 60)

                print(f"[{req_ke}/{total_request} | ETA ~{eta_menit} menit]", end=" ")

                hasil = scrape_rute(asal, tujuan, tanggal, headers_container,
                                    seat_class, num_adults, num_children, num_infants)

                # Deteksi soft block — scrape_rute mengembalikan None
                if hasil is None:
                    print(f"  REFRESH session karena soft block...")
                    cookies, csid, mcc   = get_session(
                        asal, tujuan, seat_class, num_adults, num_children, num_infants
                    )
                    headers_container[0] = build_headers(cookies, csid, mcc)
                    time.sleep(5)

                    # Retry sekali setelah refresh
                    print(f"  RETRY request setelah refresh...")
                    hasil = scrape_rute(asal, tujuan, tanggal, headers_container,
                                        seat_class, num_adults, num_children, num_infants)

                    # Kalau retry juga None/gagal, skip request ini
                    if hasil is None:
                        print(f"  Retry gagal, skip request ini.")
                        hasil = []

                # Simpan per batch langsung ke CSV — tidak tunggu semua selesai
                if hasil:
                    df_batch = pd.DataFrame(hasil)
                    df_batch.to_csv(output_file, mode="a",
                                    header=not header_written, index=False)
                    header_written = True

                # Update checkpoint setelah tiap request
                next_kelas = kelas_idx + 1
                if next_kelas >= len(seat_classes):
                    save_checkpoint(rute_idx, hari_idx + 1, 0, output_file)
                else:
                    save_checkpoint(rute_idx, hari_idx, next_kelas, output_file)

                print()
                time.sleep(2)

    clear_checkpoint()

    # Hitung total baris yang tersimpan
    df_final = pd.read_csv(output_file)
    print(f"\nSelesai! {len(df_final)} baris → {output_file}")
    print(f"Total waktu: {int((time.time() - waktu_mulai) / 60)} menit")


# ── 8. KONFIGURASI ─────────────────────────────────────────────────────────────

# dari rute populer pada halaman https://www.traveloka.com/id-id/tiket-pesawat
rute = [
    #domestik
    ("JKTA", "KNO"),  ("KNO", "JKTA"),  # Jakarta ↔ Medan
    ("JKTA", "DPS"),  ("DPS", "JKTA"),  # Jakarta ↔ Bali / Denpasar
    ("JKTA", "PKU"),  ("PKU", "JKTA"),  # Jakarta ↔ Pekanbaru
    ("JKTA", "BTH"),  ("BTH", "JKTA"),  # Jakarta ↔ Batam
    ("JKTA", "SUB"),  ("SUB", "JKTA"),  # Jakarta ↔ Surabaya
    ("JKTA", "PDG"),  ("PDG", "JKTA"),  # Jakarta ↔ Padang
    ("JKTA", "UPG"),  ("UPG", "JKTA"),  # Jakarta ↔ Makassar
    ("JKTA", "PLM"),  ("PLM", "JKTA"),  # Jakarta ↔ Palembang
    ("JKTA", "PNK"),  ("PNK", "JKTA"),  # Jakarta ↔ Pontianak

    #international
    ("JKTA", "XKLA"),  ("XKLA", "JKTA"),  # Jakarta ↔ Kuala Lumpur
    ("JKTA", "SINA"),  ("SINA", "JKTA"),  # Jakarta ↔ Singapore
    ("HAN", "SGN"),  ("SGN", "HAN"),  # Hanoi .. Ho Chi Minh City

]

scrape_semua(
    rute_list    = rute,
    hari_kedepan = 7,
    seat_classes = ALL_SEAT_CLASSES,
    num_adults   = 1,
    num_children = 0,
    num_infants  = 0,
)
