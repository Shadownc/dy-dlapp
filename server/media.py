import io
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit
from PIL import Image, UnidentifiedImageError
from flask import Response, stream_with_context


class MediaError(Exception):
    pass


def allowed_url(url, allowed_hosts):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return any(host == suffix or host.endswith("." + suffix) for suffix in allowed_hosts)
    except (ValueError, TypeError):
        return False


def resolve_public_ip(host):
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError) as exc:
        raise MediaError("媒体域名无法解析") from exc
    ips = [entry[4][0] for entry in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise MediaError("媒体域名解析到非公网地址")
    return ips[0]


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, ip, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        raw = socket.create_connection((self.ip, self.port), self.timeout)
        raw.settimeout(self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class Upstream:
    def __init__(self, conn, response):
        self.conn = conn
        self.response = response
        self.status_code = response.status
        self.headers = response.headers

    def iter_content(self, size):
        while True:
            chunk = self.response.read(size)
            if not chunk:
                return
            yield chunk

    def close(self):
        self.response.close()
        self.conn.close()


def open_media(url, settings, range_header=None):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MiniMedia/1.0)"}
    if range_header:
        if not re.fullmatch(r"bytes=\d+-\d*", range_header):
            raise MediaError("不支持该范围请求")
        headers["Range"] = range_header
    for _ in range(4):
        if not allowed_url(url, settings.media_allowed_hosts):
            raise MediaError("媒体地址不在允许的域名内")
        parsed = urlsplit(url)
        ip = resolve_public_ip(parsed.hostname)
        conn = PinnedHTTPSConnection(parsed.hostname, ip, timeout=20)
        try:
            conn.request("GET", urlunsplit(("", "", parsed.path or "/", parsed.query, "")), headers=headers)
            upstream = Upstream(conn, conn.getresponse())
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            conn.close()
            raise MediaError("媒体连接失败") from exc
        if upstream.status_code in (301, 302, 303, 307, 308):
            target = upstream.headers.get("Location", "")
            upstream.close()
            # 第三方跳转仍须经过下一轮严格的域名检查
            url = urljoin(url, target)
            continue
        if upstream.status_code not in (200, 206) or (not range_header and upstream.status_code != 200):
            upstream.close()
            raise MediaError("媒体链接已失效，请返回记录页重新解析")
        if range_header and upstream.status_code != 206:
            upstream.close()
            raise MediaError("媒体服务器不支持范围请求，请重新打开记录")
        return upstream
    raise MediaError("媒体地址跳转次数过多")


def image_response(url, settings):
    upstream = open_media(url, settings)
    try:
        content_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in ("image/webp", "image/jpeg", "image/png", "image/gif", "application/octet-stream"):
            raise MediaError("媒体服务器未返回图片")
        if int(upstream.headers.get("Content-Length", "0")) > settings.max_image_bytes:
            raise MediaError("图片超过大小限制")
        data = bytearray()
        for chunk in upstream.iter_content(65536):
            data.extend(chunk)
            if len(data) > settings.max_image_bytes:
                raise MediaError("图片超过大小限制")
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if image.width * image.height > 40_000_000:
                raise MediaError("图片分辨率过高")
            output = io.BytesIO()
            if image.mode in ("RGBA", "LA", "P"):
                rgba = image.convert("RGBA")
                base = Image.new("RGB", rgba.size, "white")
                base.paste(rgba, mask=rgba.getchannel("A"))
            else:
                base = image.convert("RGB")
            base.save(output, "JPEG", quality=90, optimize=True)
            return Response(output.getvalue(), mimetype="image/jpeg", headers={"Content-Disposition": "inline; filename=image.jpg", "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise MediaError("图片格式无法处理") from exc
    except (TypeError, ValueError) as exc:
        raise MediaError("媒体图片响应异常") from exc
    finally:
        upstream.close()


def video_response(url, settings, range_header=None):
    upstream = open_media(url, settings, range_header)
    total = upstream.headers.get("Content-Range", "")
    match = re.fullmatch(r"bytes \d+-\d+/(\d+|\*)", total)
    try:
        full_size = int(match.group(1)) if match and match.group(1) != "*" else int(upstream.headers.get("Content-Length", "0"))
    except (ValueError, TypeError):
        full_size = 0
    if full_size == 0 or full_size > settings.max_video_bytes or (upstream.status_code == 206 and not match):
        upstream.close()
        raise MediaError("视频大小未知或超过限制")
    content_type = upstream.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type not in ("video/mp4", "application/octet-stream", "binary/octet-stream"):
        upstream.close()
        raise MediaError("媒体服务器未返回 MP4")
    headers = {"Content-Disposition": "inline; filename=video.mp4", "Accept-Ranges": "bytes", "Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"}
    for source, target in (("Content-Length", "Content-Length"), ("Content-Range", "Content-Range")):
        if upstream.headers.get(source):
            headers[target] = upstream.headers[source]

    def chunks():
        count = 0
        try:
            for chunk in upstream.iter_content(65536):
                count += len(chunk)
                if count > settings.max_video_bytes:
                    return
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return Response(stream_with_context(chunks()), status=upstream.status_code, mimetype="video/mp4", headers=headers)
