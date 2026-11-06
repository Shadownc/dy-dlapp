import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read_env():
    path = ROOT / "server" / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def enabled(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes")


@dataclass
class Settings:
    host: str
    port: int
    dev_login: bool
    wx_appid: str
    wx_secret: str
    parser_api_url: str
    parser_api_method: str
    parser_api_key: str
    parser_auth_header: str
    parser_auth_prefix: str
    admin_password_hash: str
    cookie_secure: bool
    media_signing_key: str
    media_allowed_hosts: tuple
    media_token_ttl: int
    max_image_bytes: int
    max_video_bytes: int
    data_dir: Path


def load_settings():
    read_env()
    data_dir = Path(os.getenv("DATA_DIR", "server/data"))
    settings = Settings(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        dev_login=enabled("DEV_LOGIN"),
        wx_appid=os.getenv("WX_APPID", ""),
        wx_secret=os.getenv("WX_SECRET", ""),
        parser_api_url=os.getenv("PARSER_API_URL", ""),
        parser_api_method=os.getenv("PARSER_API_METHOD", "POST").upper(),
        parser_api_key=os.getenv("PARSER_API_KEY", ""),
        parser_auth_header=os.getenv("PARSER_AUTH_HEADER", "Authorization"),
        parser_auth_prefix=os.getenv("PARSER_AUTH_PREFIX", "Bearer "),
        admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH", ""),
        cookie_secure=enabled("COOKIE_SECURE", "true"),
        media_signing_key=os.getenv("MEDIA_SIGNING_KEY", ""),
        media_allowed_hosts=tuple(s.strip().lower() for s in os.getenv("MEDIA_ALLOWED_HOSTS", "douyinpic.com,douyinvod.com,zjcdn.com").split(",") if s.strip()),
        media_token_ttl=int(os.getenv("MEDIA_TOKEN_TTL", "1200")),
        max_image_bytes=int(os.getenv("MAX_IMAGE_BYTES", "20971520")),
        max_video_bytes=int(os.getenv("MAX_VIDEO_BYTES", "125829120")),
        data_dir=data_dir if data_dir.is_absolute() else ROOT / data_dir,
    )
    if settings.dev_login and settings.host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("DEV_LOGIN 仅允许监听本机")
    if not settings.dev_login and (not settings.wx_appid or not settings.wx_secret or not settings.media_signing_key or not settings.cookie_secure):
        raise ValueError("生产环境须配置微信凭据、MEDIA_SIGNING_KEY 且 COOKIE_SECURE=true")
    if not settings.dev_login and len(settings.media_signing_key) < 32:
        raise ValueError("MEDIA_SIGNING_KEY 至少 32 位")
    if settings.parser_api_method not in ("POST", "GET"):
        raise ValueError("PARSER_API_METHOD 只能为 GET 或 POST")
    return settings
