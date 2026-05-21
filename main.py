# app/main.py
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import traceback
import math

from pathlib import Path
from scraper import Scraper
from utils import normalize_scraper_result
from cache import (
    variant_key, get_variant, put_variant,
    load_shard, save_shard, gc_shard
)

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True

scraper = Scraper()
scheduler = BackgroundScheduler(timezone="UTC")

# -------------------------------
# Util: parse & compose varian key
# -------------------------------
def _parse_variant_key(vkey: str) -> dict:
    """
    Parse key bentuk:
      page=1|jt=fulltime,magang|wo=remote|loc=all
    jadi dict parameter untuk scraper.
    """
    out = {"page": 1, "job_type": "", "work_option": "", "location_id": "all"}
    try:
        parts = vkey.split("|")
        for p in parts:
            if "=" not in p:
                continue
            k, v = p.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "page":
                out["page"] = int(v or "1")
            elif k == "jt":
                out["job_type"] = v
            elif k == "wo":
                out["work_option"] = v
            elif k == "loc":
                out["location_id"] = v or "all"
    except Exception:
        pass
    return out

# -------------------------------
# Halaman depan
# -------------------------------
@app.route("/")
def home():
    return render_template("index.html")

# -------------------------------
# GLINTS
# -------------------------------
@app.route("/glints", methods=["GET"])
def route_glints():
    try:
        params = {
            "work": request.args.get("work", "Programmer"),
            "job_type": request.args.get("job_type", ""),
            "work_option": request.args.get("work_option", ""),
            "location_id": request.args.get("location_id", "all"),
            "page": int(request.args.get("page", 1)),
        }
        vkey = variant_key(
            page=params["page"],
            job_type=params["job_type"],
            work_option=params["work_option"],
            location_id=params["location_id"],
        )

        cached, _shard = get_variant(params["work"], "glints", vkey)
        if cached:
            if request.args.get("debug") == "1":
                return jsonify({"_debug": {"cached": True, "source": "glints", "vkey": vkey, "params": params}, **cached})
            return jsonify(cached)

        payload = normalize_scraper_result(scraper.search_glints(**params))
        put_variant(params["work"], "glints", vkey, payload)

        if request.args.get("debug") == "1":
            return jsonify({"_debug": {"cached": False, "source": "glints", "vkey": vkey, "params": params}, **payload})
        return jsonify(payload)
    except Exception as e:
        app.logger.error("Error in /glints", exc_info=True)
        return jsonify({"status": False, "message": str(e)}), 500

# -------------------------------
# JOBSTREET
# -------------------------------
@app.route("/jobstreet", methods=["GET"])
def route_jobstreet():
    try:
        params = {
            "work": request.args.get("work", "Programmer"),
            "work_option": request.args.get("work_option", ""),
            "job_type": request.args.get("job_type", ""),
            "page": int(request.args.get("page", 1)),
        }
        vkey = variant_key(
            page=params["page"],
            job_type=params["job_type"],
            work_option=params["work_option"],
            location_id="all",
        )

        cached, _shard = get_variant(params["work"], "jobstreet", vkey)
        if cached:
            if request.args.get("debug") == "1":
                return jsonify({"_debug": {"cached": True, "source": "jobstreet", "vkey": vkey, "params": params}, **cached})
            return jsonify(cached)

        payload = normalize_scraper_result(scraper.search_jobstreet(**params))
        put_variant(params["work"], "jobstreet", vkey, payload)

        if request.args.get("debug") == "1":
            return jsonify({"_debug": {"cached": False, "source": "jobstreet", "vkey": vkey, "params": params}, **payload})
        return jsonify(payload)
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        return jsonify({"status": False, "message": str(e)}), 500

# -------------------------------
# KARIR.COM
# -------------------------------
@app.route("/karir", methods=["GET"])
def route_karir():
    try:
        params = {
            "work": request.args.get("work", "Programmer"),
            "work_option": request.args.get("work_option", ""),
            "page": int(request.args.get("page", 1)),
            "cookies_file": request.args.get("cookies_file", "config/karir.json"),
        }
        vkey = variant_key(
            page=params["page"],
            job_type="", 
            work_option=params["work_option"],
            location_id="all",
        )

        cached, _shard = get_variant(params["work"], "karir", vkey)
        if cached:
            if request.args.get("debug") == "1":
                return jsonify({"_debug": {"cached": True, "source": "karir", "vkey": vkey, "params": params}, **cached})
            return jsonify(cached)

        payload = normalize_scraper_result(scraper.search_karir(**params))
        put_variant(params["work"], "karir", vkey, payload)

        if request.args.get("debug") == "1":
            return jsonify({"_debug": {"cached": False, "source": "karir", "vkey": vkey, "params": params}, **payload})
        return jsonify(payload)
    except Exception as e:
        app.logger.error("Error in /karir", exc_info=True)
        return jsonify({"status": False, "message": str(e)}), 500


def _merge_results(res_list):
    """
    Gabungkan jobs dari beberapa payload.
    Tetap kembalikan struktur {status, data:{jobs, pagination}}
    """
    seen = set()
    jobs = []
    for res in res_list:
        if not res or not isinstance(res, dict):
            continue
        ok = res.get("status")
        data = res.get("data", {}) if ok else {}
        items = data.get("jobs", [])
        for j in items:
            uid = (j.get("link") or "") or (j.get("title","")+j.get("company_name",""))
            if uid in seen:
                continue
            seen.add(uid)
            jobs.append(j)
    return {"status": True, "data": {"jobs": jobs, "pagination": None}}

@app.route("/all", methods=["GET"])
def route_all_sources():
    """
    Endpoint opsional untuk menghimpun tiga sumber sekaligus.
    Ikuti parameter umum: work, job_type, work_option, location_id, page
    """
    try:
        work = request.args.get("work", "Programmer")
        job_type = request.args.get("job_type", "")
        work_option = request.args.get("work_option", "")
        location_id = request.args.get("location_id", "all")
        page = int(request.args.get("page", 1))

        v_glints = variant_key(page=page, job_type=job_type, work_option=work_option, location_id=location_id)
        v_jobst = variant_key(page=page, job_type=job_type, work_option=work_option, location_id="all")
        v_karir = variant_key(page=page, job_type="",       work_option=work_option, location_id="all")

        out_payloads = []

        # --- GLINTS ---
        cached, _ = get_variant(work, "glints", v_glints)
        if not cached:
            p = normalize_scraper_result(scraper.search_glints(work=work, job_type=job_type, work_option=work_option, location_id=location_id, page=page))
            put_variant(work, "glints", v_glints, p)
            out_payloads.append(p)
        else:
            out_payloads.append(cached)

        # --- JOBSTREET ---
        cached, _ = get_variant(work, "jobstreet", v_jobst)
        if not cached:
            p = normalize_scraper_result(scraper.search_jobstreet(work=work, work_option=work_option, job_type=job_type, page=page))
            put_variant(work, "jobstreet", v_jobst, p)
            out_payloads.append(p)
        else:
            out_payloads.append(cached)

        # --- KARIR ---
        cached, _ = get_variant(work, "karir", v_karir)
        if not cached:
            p = normalize_scraper_result(scraper.search_karir(work=work, work_option=work_option, page=page, cookies_file=request.args.get("cookies_file","config/karir.json")))
            put_variant(work, "karir", v_karir, p)
            out_payloads.append(p)
        else:
            out_payloads.append(cached)

        merged = _merge_results(out_payloads)
        per_page = int(request.args.get("per_page", 24))
        all_jobs = merged.get("data", {}).get("jobs", [])
        total = len(all_jobs)
        if total == 0:
            merged["data"]["pagination"] = {
                "current_page": 1,
                "last_page": 1,
                "has_next": False,
                "total": 0,
                "per_page": per_page
            }
        else:
            page = max(1, int(request.args.get("page", 1)))
            last_page = max(1, math.ceil(total / per_page))
            if page > last_page:
                page = last_page

            start = (page - 1) * per_page
            end = start + per_page

            merged["data"]["jobs"] = all_jobs[start:end]
            merged["data"]["pagination"] = {
                "current_page": page,
                "last_page": last_page,
                "has_next": page < last_page,
                "total": total,
                "per_page": per_page
            }

        if request.args.get("debug") == "1":
            return jsonify({"_debug": {
                "glints_vkey": v_glints,
                "jobstreet_vkey": v_jobst,
                "karir_vkey": v_karir,
                "work": work, "job_type": job_type, "work_option": work_option, "location_id": location_id, "page": page,
                "per_page": per_page,
            }, **merged})
        return jsonify(merged)

    except Exception as e:
        app.logger.exception("Error in /all")
        return jsonify({"status": False, "message": str(e)}), 500

# --------------------------------------------------------
# SCHEDULER: refresh varian yang sudah kedaluwarsa (TTL 24 jam)
# --------------------------------------------------------
def _refresh_shard(keyword: str, source: str):
    """
    Baca shard (per keyword + per source), untuk setiap varian:
    - Jika stale → fetch ulang dengan memetakan kembali parameter dari vkey,
      kemudian simpan.
    - Jika tidak stale → lewati.
    Setelah itu jalankan GC untuk bersih-bersih varian yang kadaluarsa.
    """
    shard = load_shard(keyword, source)
    variants = shard.get("variants", {})
    changed = False

    for vkey, entry in list(variants.items()):
        cached, _ = get_variant(keyword, source, vkey)
        if cached:
            continue  

        vparams = _parse_variant_key(vkey)
        page = int(vparams.get("page", 1))
        job_type = vparams.get("job_type", "")
        work_option = vparams.get("work_option", "")
        location_id = vparams.get("location_id", "all")

        try:
            if source == "glints":
                payload = normalize_scraper_result(scraper.search_glints(
                    work=keyword, job_type=job_type, work_option=work_option,
                    location_id=location_id, page=page
                ))
            elif source == "jobstreet":
                payload = normalize_scraper_result(scraper.search_jobstreet(
                    work=keyword, work_option=work_option, job_type=job_type, page=page
                ))
            elif source == "karir":
                payload = normalize_scraper_result(scraper.search_karir(
                    work=keyword, work_option=work_option, page=page, cookies_file="config/karir.json"
                ))
            else:
                continue

            shard["variants"][vkey] = {"ts": datetime.utcnow().isoformat() + "Z", "data": payload}
            changed = True
            app.logger.info("Refreshed shard var: %s.%s [%s]", keyword, source, vkey)
        except Exception:
            app.logger.exception("Failed to refresh shard var: %s.%s [%s]", keyword, source, vkey)

    if changed:
        save_shard(keyword, source, shard)

    try:
        gc_shard(keyword, source)
    except Exception:
        app.logger.exception("GC shard failed for %s.%s", keyword, source)

def _iter_shards():
    # Coba ambil shard keys dari Redis jika terhubung ke Vercel KV
    try:
        from cache import redis_client
        if redis_client:
            keys = redis_client.keys("shard:*")
            for k in keys:
                if isinstance(k, bytes):
                    k = k.decode("utf-8")
                parts = k.split(":")
                if len(parts) == 3:
                    yield parts[1], parts[2]
            return
    except Exception as e:
        app.logger.error("Failed to fetch shard keys from Vercel KV: %s", str(e))

    # Fallback ke filesystem lokal
    PROJECT_ROOT = Path(__file__).resolve().parent
    base = Path(os.environ.get("SCRAPER_SHARDS_DIR", PROJECT_ROOT / "data" / "shards")).resolve()
    if not os.path.isdir(base):
        return
    for fname in os.listdir(base):
        if not fname.endswith(".json"):
            continue
        try:
            name = fname[:-5]
            keyword, source = name.rsplit(".", 1)
            yield keyword, source
        except Exception:
            continue

def refresh_all_shards():
    app.logger.info("Daily refresh started")
    for keyword, source in _iter_shards():
        try:
            _refresh_shard(keyword, source)
        except Exception:
            app.logger.exception("Refresh failed for shard %s.%s", keyword, source)
    app.logger.info("Daily refresh finished")

@app.route("/admin/refresh", methods=["GET"])
def admin_refresh():
    # Amankan endpoint jika berjalan di Vercel dan CRON_SECRET dikonfigurasi
    IS_VERCEL = os.environ.get("VERCEL") == "1"
    cron_secret = os.environ.get("CRON_SECRET")
    if IS_VERCEL and cron_secret:
        auth_header = request.headers.get("Authorization")
        if auth_header != f"Bearer {cron_secret}":
            return jsonify({"status": False, "message": "Unauthorized"}), 401

    try:
        refresh_all_shards()
        return jsonify({"status": True, "message": "Manual refresh done"})
    except Exception as e:
        app.logger.exception("Manual refresh error")
        return jsonify({"status": False, "message": str(e)}), 500
        
def start_scheduler():
    # Jangan jalankan background thread scheduler di lingkungan Vercel
    if os.environ.get("VERCEL") == "1":
        app.logger.info("Background scheduler disabled on Vercel serverless environment")
        return
    scheduler.add_job(refresh_all_shards, "interval", hours=24, next_run_time=None)
    scheduler.start()
    
def create_app():
    start_scheduler()
    return app
    
if __name__ == "__main__":
    start_scheduler()
    app.run(host="0.0.0.0", port=5050)
