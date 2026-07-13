import hashlib

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def http_get(url):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    return r


def make_id(source, key):
    return hashlib.sha1(f"{source}|{key}".encode("utf-8")).hexdigest()[:12]
