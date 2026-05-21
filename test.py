from singletons.cloudscrapper import CloudScraper
import json

url = "https://twplay.redfinger.com/osfingerauth/activation/checkActivationCode.json?lang=in&client=web&uuid=db4bf522-e97d-4e23-8287-2522e27fbcdf&versionName=2.47.14&versionCode=200470014&languageType=in&sessionId=92f020888d3043cba8e7b35cbe602e2a&userId=10227301&channelCode=web&serverNode=tw&timestamp=1762864089784&userSource=web&medium=organic&campaign=organic&sign=3ecba854d50bd4484d947a15a68dca52"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "Api-Version": "200470014",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Authorization": "10227301 92f020888d3043cba8e7b35cbe602e2a",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Host": "twplay.redfinger.com",
    "Server-Node": "tw",
    "Origin": "https://www.cloudemulator.net",
    "Referer": "https://www.cloudemulator.net/"
}

payload = {"code": "TML4TJR2UD58", "bizType": 0, "goodsOptionsTypeValueJson": {"rom_version":"10.0","idc_code":"SG_IDC_03"}}

scraper = CloudScraper.get_instance("config/rf.json")
# r = scraper.post(url, data = json.dumps(payload), headers=headers)
r = scraper.get("https://twplay.redfinger.com/osfingerauth/user/getUserInfo.html?lang=in&client=web&uuid=db4bf522-e97d-4e23-8287-2522e27fbcdf&versionName=2.47.14&versionCode=200470014&languageType=in&sessionId=92f020888d3043cba8e7b35cbe602e2a&userId=10227301&channelCode=web&serverNode=tw&timestamp=1762864639645&userSource=web&medium=organic&campaign=organic&sign=fc5c5870630ceff3c597650de3f84c5f", headers=headers)
print(r)
print(r.text)