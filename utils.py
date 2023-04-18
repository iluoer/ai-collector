# -*- coding: utf-8 -*-

# @Author  : wzdnzd
# @Time    : 2022-07-15

import gzip
import json
import os
import re
import ssl
import time
import urllib
import urllib.parse
import urllib.request
from http.client import HTTPResponse

from logger import logger
from urlvalidator import isurl

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"


def http_get(
    url: str,
    headers: dict = None,
    params: dict = None,
    retry: int = 3,
    proxy: str = "",
    interval: float = 0,
) -> str:
    if not isurl(url=url):
        logger.error(f"invalid url: {url}")
        return ""

    if retry <= 0:
        logger.debug(f"achieves max retry, url={url}")
        return ""

    if not headers:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        }

    interval = max(0, interval)
    try:
        url = encoding_url(url=url)
        if params and isinstance(params, dict):
            data = urllib.parse.urlencode(params)
            if "?" in url:
                url += f"&{data}"
            else:
                url += f"?{data}"

        request = urllib.request.Request(url=url, headers=headers)
        if proxy and (proxy.startswith("https://") or proxy.startswith("http://")):
            host, protocal = "", ""
            if proxy.startswith("https://"):
                host, protocal = proxy[8:], "https"
            else:
                host, protocal = proxy[7:], "http"
            request.set_proxy(host=host, type=protocal)

        response = urllib.request.urlopen(request, timeout=10, context=CTX)
        content = response.read()
        status_code = response.getcode()
        try:
            content = str(content, encoding="utf8")
        except:
            content = gzip.decompress(content).decode("utf8")
        if status_code != 200:
            logger.debug(
                f"request failed, status code: {status_code}\t message: {content}"
            )
            return ""

        return content
    except urllib.error.HTTPError as e:
        logger.debug(f"request failed, url=[{url}], code: {e.code}")
        try:
            message = str(e.read(), encoding="utf8")
        except UnicodeDecodeError:
            message = str(e.read(), encoding="utf8")
        if e.code == 503 and "token" not in message:
            time.sleep(interval)
            return http_get(
                url=url,
                headers=headers,
                params=params,
                retry=retry - 1,
                proxy=proxy,
                interval=interval,
            )
        return ""
    except urllib.error.URLError as e:
        logger.debug(f"request failed, url=[{url}], message: {e.reason}")
        return ""
    except Exception as e:
        logger.error(e)
        time.sleep(interval)
        return http_get(
            url=url,
            headers=headers,
            params=params,
            retry=retry - 1,
            proxy=proxy,
            interval=interval,
        )


def http_post(
    url: str,
    headers: dict = None,
    params: dict = {},
    retry: int = 3,
) -> HTTPResponse:
    if retry <= 0 or params is None or type(params) != dict:
        return None

    if not headers:
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }
    try:
        data = json.dumps(params).encode(encoding="UTF8")
        request = urllib.request.Request(
            url=url, data=data, headers=headers, method="POST"
        )
        return urllib.request.urlopen(request, timeout=30, context=CTX)
    except urllib.error.HTTPError as e:
        logger.debug(f"request failed, url=[{url}], code: {e.code}")
        if e.code in [401, 404]:
            return None

        return http_post(url=url, headers=headers, params=params, retry=retry - 1)
    except urllib.error.URLError as e:
        logger.debug(f"request failed, url=[{url}], message: {e.reason}")
        return None
    except Exception:
        return http_post(url=url, headers=headers, params=params, retry=retry - 1)


def extract_domain(url: str, include_protocal: bool = False) -> str:
    if not url:
        return ""

    start = url.find("//")
    if start == -1:
        start = -2

    end = url.find("/", start + 2)
    if end == -1:
        end = len(url)

    if include_protocal:
        return url[:end]

    return url[start + 2 : end]


def encoding_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    # 正则匹配中文汉字
    cn_chars = re.findall("[\u4e00-\u9fa5]+", url)
    if not cn_chars:
        return url

    # 遍历进行 punycode 编码
    punycodes = list(
        map(lambda x: "xn--" + x.encode("punycode").decode("utf-8"), cn_chars)
    )

    # 对原 url 进行替换
    for c, pc in zip(cn_chars, punycodes):
        url = url[: url.find(c)] + pc + url[url.find(c) + len(c) :]

    return url


def isblank(text: str) -> bool:
    return not text or type(text) != str or not text.strip()


def load_dotenv() -> None:
    path = os.path.abspath(os.path.dirname(__file__))
    filename = os.path.join(path, ".env")

    if not os.path.exists(filename) or os.path.isdir(filename):
        return

    with open(filename, mode="r", encoding="utf8") as f:
        for line in f.readlines():
            content = line.strip()
            if not content or content.startswith("#") or "=" not in content:
                continue
            words = content.split("=", maxsplit=1)
            k, v = words[0].strip(), words[1].strip()
            if k and v:
                os.environ[k] = v
