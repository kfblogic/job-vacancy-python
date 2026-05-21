import os
import re
import json
from typing import Any, Dict, List, Tuple

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "all"

def slugify_params(params: Dict[str, Any]) -> str:
    items: List[Tuple[str, str]] = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, (dict, list)):
            v = json.dumps(v, sort_keys=True, ensure_ascii=False)
        items.append(f"{slugify(k)}_{slugify(str(v))}")
    base = "__".join(items)
    return base[:200] 

def normalize_scraper_result(result: Any) -> Dict[str, Any]:
    """
    Helper untuk memastikan bentuk dict.
    - Jika sudah dict → kembalikan
    - Jika tuple (body, status) → ambil body
    - Jika objek Flask Response → coba .get_json(silent=True)
    """
    try:
        if isinstance(result, dict):
            return result
        if isinstance(result, tuple) and len(result) >= 1 and isinstance(result[0], dict):
            return result[0]
        get_json = getattr(result, "get_json", None)
        if callable(get_json):
            data = result.get_json(silent=True)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"status": "failed", "message": "Unrecognized scraper response"}
