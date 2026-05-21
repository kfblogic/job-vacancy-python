# app/cache_sharded.py
import json, os, threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("SCRAPER_SHARDS_DIR", PROJECT_ROOT / "data" / "shards")).resolve()
LOCK = threading.Lock()
TTL = timedelta(hours=24)

# Deteksi lingkungan Vercel (filesystem read-only)
IS_VERCEL = os.environ.get("VERCEL") == "1"

# Inisialisasi Vercel KV jika dikonfigurasi di environment
KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")

redis_client = None
if KV_URL and KV_TOKEN:
    try:
        from upstash_redis import Redis
        redis_client = Redis(url=KV_URL, token=KV_TOKEN)
    except ImportError:
        # Fallback jika library belum di-install saat run local dev
        pass

def _empty_shard(keyword: str, source: str) -> dict:
    """Return struktur shard kosong tanpa menyentuh disk."""
    return {"_meta": {"keyword": keyword, "source": source, "updated_utc": _iso(_now())}, "variants": {}}

def _now():
    return datetime.now(timezone.utc)

def _iso(dt):  return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _slug_kw(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s.strip().lower()) or "all"

def _redis_key(keyword: str, source: str) -> str:
    return f"shard:{_slug_kw(keyword)}:{source.lower()}"

def _shard_path(keyword: str, source: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{_slug_kw(keyword)}.{source.lower()}.json")

def _canon_list(csv: str) -> str:
    items = [x.strip().lower() for x in csv.split(",") if x.strip()]
    return ",".join(sorted(set(items)))

def variant_key(*, page:int, job_type:str, work_option:str, location_id:str) -> str:
    return f"page={int(page)}|jt={_canon_list(job_type)}|wo={_canon_list(work_option)}|loc={(location_id or '').strip().lower() or 'all'}"

def load_shard(keyword: str, source: str) -> dict:
    # 1) Coba Redis terlebih dahulu
    if redis_client:
        try:
            key = _redis_key(keyword, source)
            val = redis_client.get(key)
            if val:
                if isinstance(val, dict):
                    return val
                return json.loads(val)
        except Exception as e:
            print(f"[KV Connection Error] load_shard: {e}")

    # 2) Di Vercel tanpa Redis → kembalikan shard kosong, JANGAN sentuh disk
    if IS_VERCEL:
        return _empty_shard(keyword, source)

    # 3) Fallback ke filesystem lokal (hanya saat development)
    path = _shard_path(keyword, source)
    if not os.path.exists(path):
        return _empty_shard(keyword, source)
    with LOCK, open(path, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except json.JSONDecodeError:
            return _empty_shard(keyword, source)

def save_shard(keyword: str, source: str, shard: dict):
    shard["_meta"]["updated_utc"] = _iso(_now())

    # 1) Coba Redis terlebih dahulu
    if redis_client:
        try:
            key = _redis_key(keyword, source)
            redis_client.set(key, json.dumps(shard, ensure_ascii=False), ex=7*24*60*60)
            return
        except Exception as e:
            print(f"[KV Connection Error] save_shard: {e}")

    # 2) Di Vercel tanpa Redis → skip, tidak bisa menulis ke disk
    if IS_VERCEL:
        print("[Warning] save_shard skipped: Vercel read-only filesystem and no KV connected")
        return

    # 3) Fallback ke filesystem lokal (hanya saat development)
    path = _shard_path(keyword, source)
    with LOCK, open(path, "w", encoding="utf-8") as f:
        json.dump(shard, f, ensure_ascii=False, indent=2)

def get_variant(keyword:str, source:str, vkey:str):
    shard = load_shard(keyword, source)
    entry = shard["variants"].get(vkey)
    if not entry: return None, shard
    try:
        ts = datetime.fromisoformat(entry["ts"].replace("Z","+00:00"))
    except Exception:
        return None, shard
    if _now() - ts >= TTL:
        return None, shard  # stale
    return entry["data"], shard

def put_variant(keyword:str, source:str, vkey:str, payload:dict):
    shard = load_shard(keyword, source)
    shard["variants"][vkey] = {"ts": _iso(_now()), "data": payload}
    save_shard(keyword, source, shard)

def gc_shard(keyword:str, source:str):
    shard = load_shard(keyword, source)
    stale_keys = []
    for k, v in shard["variants"].items():
        try:
            ts = datetime.fromisoformat(v["ts"].replace("Z","+00:00"))
            if _now() - ts >= TTL: stale_keys.append(k)
        except Exception:
            stale_keys.append(k)
    for k in stale_keys: shard["variants"].pop(k, None)
    if stale_keys: save_shard(keyword, source, shard)
