"""
app.py — Flask API Server untuk Web Prediksi Harga Tiket Pesawat
Jalankan: python script/app.py
Buka browser: http://localhost:5000
"""

import os
import sys
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend import AIRPORT_NAMES, AIRLINE_NAMES, CLASS_LABELS, FlightPredictor

# ---------------------------------------------------------------------------
# Inisialisasi
# ---------------------------------------------------------------------------

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    static_url_path="/static",
)

print("⟳  Loading FlightPredictor model...", flush=True)
predictor = FlightPredictor()
print("✓  Model ready.\n", flush=True)


# ---------------------------------------------------------------------------
# Helper: standard JSON response
# ---------------------------------------------------------------------------

def ok(data):
    return jsonify({"status": "ok", "data": data})


def err(msg: str, code: int = 400):
    return jsonify({"status": "error", "message": msg}), code


# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route("/api/airports/origin", methods=["GET"])
def api_airports_origin():
    """Daftar semua bandara asal yang valid."""
    origins = predictor.get_valid_origins()
    result = [
        {"code": code, "name": AIRPORT_NAMES.get(code, code)}
        for code in origins
    ]
    return ok(result)


@app.route("/api/airports/dest", methods=["GET"])
def api_airports_dest():
    """
    Daftar semua bandara tujuan yang valid.
    Hanya exclude bandara yang sama dengan asal (agar tidak CGK→CGK).
    Tidak lagi dibatasi hanya rute yang ada di data historis.
    """
    origin = request.args.get("origin")
    dests = predictor.get_valid_destinations(origin if origin else None)
    result = [
        {"code": code, "name": AIRPORT_NAMES.get(code, code)}
        for code in dests
    ]
    return ok(result)


@app.route("/api/airlines", methods=["GET"])
def api_airlines():
    """
    Semua maskapai yang valid — tidak dibatasi per rute.
    Free routing: user bisa pilih maskapai apa pun untuk rute apa pun.
    Mengembalikan flag `existing` jika origin dan dest diberikan.
    """
    origin = request.args.get("origin")
    dest = request.args.get("dest")

    airlines = predictor.get_valid_airlines(include_all=True)
    existing_airlines = set()
    
    if origin and dest:
        route_mask = (predictor.df["bandara_asal"] == origin) & (predictor.df["bandara_tujuan"] == dest)
        existing_airlines = set(predictor.df[route_mask]["maskapai_final"].unique().tolist())

    result = []
    for code in airlines:
        name = AIRLINE_NAMES.get(code, code) if code != "ALL" else "Semua Maskapai"
        if code == "ALL":
            is_existing = True
        else:
            is_existing = (code in existing_airlines) if (origin and dest) else True
            
        result.append({
            "code": code,
            "name": name,
            "existing": is_existing
        })

    return ok(result)


@app.route("/api/classes", methods=["GET"])
def api_classes():
    """Kelas penerbangan yang tersedia untuk maskapai tertentu."""
    airline = request.args.get("airline")
    classes = predictor.get_valid_classes(airline if airline and airline != "ALL" else None)
    result = [
        {"code": code, "name": CLASS_LABELS.get(code, code)}
        for code in classes
    ]
    return ok(result)


@app.route("/api/route/check", methods=["GET"])
def api_route_check():
    """Cek apakah rute origin→dest ada di data historis."""
    origin = request.args.get("origin", "").upper()
    dest   = request.args.get("dest",   "").upper()
    exists = predictor.is_existing_route(origin, dest)
    jarak  = predictor._calc_jarak_km(origin, dest) if origin and dest else None
    return ok({"exists": exists, "jarak_km": round(jarak, 1) if jarak else None})


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """
    Endpoint prediksi utama.
    Body JSON:
    {
        "origin": "CGK",
        "dest": "KNO",
        "tanggal_berangkat": "2026-06-15",
        "tanggal_pulang": "2026-06-20",   // opsional
        "airline": "ALL",
        "kelas": "ECONOMY",
        "is_transit": null,               // null=semua, 0=langsung, 1=transit
        "n": 5
    }
    """
    body = request.get_json(force=True, silent=True)
    if not body:
        return err("Request body JSON tidak valid.")

    # Validasi field wajib
    required = ["origin", "dest", "tanggal_berangkat", "airline", "kelas"]
    for field in required:
        if field not in body:
            return err(f"Field '{field}' wajib diisi.")

    origin = str(body["origin"]).upper()
    dest = str(body["dest"]).upper()
    airline = str(body.get("airline", "ALL"))
    kelas = str(body.get("kelas", "ECONOMY")).upper()
    is_transit_raw = body.get("is_transit")  # null, 0, 1
    is_transit = None if is_transit_raw is None else int(is_transit_raw)
    n = max(1, min(10, int(body.get("n", 5))))
    tanggal_berangkat_str = str(body["tanggal_berangkat"])
    tanggal_pulang_str = body.get("tanggal_pulang")
    
    is_advanced = body.get("is_advanced", False)
    adv_feats = body.get("advanced_features", {})

    # Parse tanggal
    try:
        tgl_brgkt = datetime.strptime(tanggal_berangkat_str, "%Y-%m-%d").date()
    except ValueError:
        return err("Format tanggal_berangkat tidak valid. Gunakan YYYY-MM-DD.")

    tgl_pulang = None
    if tanggal_pulang_str:
        try:
            tgl_pulang = datetime.strptime(str(tanggal_pulang_str), "%Y-%m-%d").date()
            if tgl_pulang <= tgl_brgkt:
                return err("tanggal_pulang harus setelah tanggal_berangkat.")
        except ValueError:
            return err("Format tanggal_pulang tidak valid. Gunakan YYYY-MM-DD.")

    # Prediksi berangkat
    try:
        if is_advanced:
            result_go = predictor.predict_advanced(
                origin=origin,
                dest=dest,
                tanggal_terbang=tgl_brgkt,
                airline=airline,
                kelas=kelas,
                adv_feats=adv_feats,
            )
        else:
            result_go = predictor.search(
                origin=origin,
                dest=dest,
                tanggal_terbang=tgl_brgkt,
                airline=airline,
                kelas=kelas,
                is_transit=is_transit,
                n=n,
            )
    except ValueError as e:
        return err(str(e))

    response = {
        "berangkat": result_go,
        "pulang": None,
    }

    # Prediksi pulang (jika ada)
    if tgl_pulang:
        try:
            if is_advanced:
                result_back = predictor.predict_advanced(
                    origin=dest,
                    dest=origin,
                    tanggal_terbang=tgl_pulang,
                    airline=airline,
                    kelas=kelas,
                    adv_feats=adv_feats,
                )
            else:
                result_back = predictor.search(
                    origin=dest,
                    dest=origin,
                    tanggal_terbang=tgl_pulang,
                    airline=airline,
                    kelas=kelas,
                    is_transit=is_transit,
                    n=n,
                )
            response["pulang"] = result_back
        except ValueError as e:
            response["pulang"] = {"tickets": [], "warnings": [str(e)], "params": {}}

    return ok(response)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀  Server berjalan di http://localhost:{port}")
    app.run(host="0.0.0.0", debug=False, port=port, use_reloader=False, threaded=True)
