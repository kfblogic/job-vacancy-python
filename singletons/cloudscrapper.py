import cloudscraper
from helpers.cookie_helper import load_cookies

class CloudScraper:
    _instance = None
    _default_cookies_file = 'app/config/sample_cookie.json'

    @staticmethod
    def get_instance(cookies_file=None):
        """
        Mendapatkan instance cloudscraper yang sudah diinisialisasi.
        Jika cookies_file diberikan, file tersebut digunakan untuk cookies.
        """
        if CloudScraper._instance is None:
            CloudScraper(cookies_file)
        return CloudScraper._instance

    def __init__(self, cookies_file=None):
        if CloudScraper._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            # Inisialisasi cloudscraper
            scraper = cloudscraper.create_scraper()

            # Tentukan file cookies
            if cookies_file is None:
                cookies_file = CloudScraper._default_cookies_file

            # Memuat cookies
            try:
                cookies = load_cookies(cookies_file)
                scraper.cookies = cookies
            except Exception as e:
                raise Exception(f"Failed to load cookies from {cookies_file}: {str(e)}")

            scraper.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
                'Connection': 'keep-alive'
            })

            CloudScraper._instance = scraper
