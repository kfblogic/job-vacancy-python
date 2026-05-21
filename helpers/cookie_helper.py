import json
from requests.cookies import RequestsCookieJar
import os

def load_cookies(file_path):
    """
    Memuat cookies dari file JSON dan mengembalikannya sebagai RequestsCookieJar.
    """
    jar = RequestsCookieJar()
    
    # Pastikan file cookies ada
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File cookies tidak ditemukan: {file_path}")
    
    with open(file_path, 'r') as f:
        cookies = json.load(f)
    
    for cookie in cookies:
        jar.set(
            name=cookie.get('name'),
            value=cookie.get('value'),
            domain=cookie.get('domain', ''),
            path=cookie.get('path', '/'),
            secure=cookie.get('secure', True),
            rest={'HttpOnly': cookie.get('httpOnly', True)}
        )
    
    return jar
