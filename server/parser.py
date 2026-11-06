import re
from urllib.parse import urlsplit

import requests


LINK_PATTERN = re.compile(r"https?://[^\s<>\"'，。；！？]+", re.I)


class ParseError(Exception):
    pass


def extract_share_link(text):
    if not isinstance(text, str) or len(text) > 3000:
        raise ParseError("分享内容过长或格式错误")
    for match in LINK_PATTERN.finditer(text):
        link = match.group(0).rstrip(".,;!?)]}")
        host = (urlsplit(link).hostname or "").lower()
        if host == "douyin.com" or host.endswith(".douyin.com") or host == "iesdouyin.com" or host.endswith(".iesdouyin.com"):
            if urlsplit(link).scheme == "https" and len(link) <= 2048:
                return link
    raise ParseError("请粘贴抖音 HTTPS 分享链接")


def call_parser(link, settings):
    if not settings.parser_api_url:
        raise ParseError("解析服务尚未配置，请联系管理员")
    headers = {"Accept": "application/json"}
    if settings.parser_api_key:
        prefix = settings.parser_auth_prefix
        if prefix and not prefix[-1].isspace():
            prefix += " "
        headers[settings.parser_auth_header] = prefix + settings.parser_api_key
    try:
        if settings.parser_api_method == "GET":
            response = requests.get(settings.parser_api_url, params={"url": link}, headers=headers, timeout=(5, 25))
        else:
            response = requests.post(settings.parser_api_url, json={"url": link}, headers=headers, timeout=(5, 25))
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ParseError("解析服务暂时不可用，请稍后重试") from exc
    if not isinstance(data, dict) or data.get("status") != "success":
        raise ParseError("未能解析该作品，请确认分享链接有效")
    if data.get("type") not in ("video", "image_album") or not isinstance(data.get("content"), list):
        raise ParseError("解析结果格式不受支持")
    if not data["content"] or len(data["content"]) > 100:
        raise ParseError("解析结果为空或内容数量超限")
    aweme_id = str(data.get("aweme_id", ""))
    if not re.fullmatch(r"\d{1,32}", aweme_id):
        raise ParseError("解析结果缺少有效的作品 ID")
    content = []
    for item in data["content"]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            raise ParseError("解析结果中的媒体格式有误")
        row = {"url": item["url"]}
        for field in ("video", "thumbnail"):
            if isinstance(item.get(field), str) and item[field]:
                row[field] = item[field]
        content.append(row)
    return {"aweme_id": aweme_id, "title": str(data.get("title") or "无标题")[:200], "type": data["type"], "content": content}
