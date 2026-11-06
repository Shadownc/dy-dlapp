import hashlib
import os
import secrets
import threading
import time
from functools import wraps

import requests
from flask import Flask, jsonify, request, send_from_directory, g
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .db import Database
from .hash_password import check_hash
from .media import MediaError, allowed_url, image_response, video_response
from .parser import ParseError, call_parser, extract_share_link
from .settings import ROOT, load_settings


def now():
    return int(time.time())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def failure(message, status=400):
    return jsonify({"error": message}), status


def create_app(settings=None, parser_fn=None):
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.config["MAX_CONTENT_LENGTH"] = 32768
    db = Database(settings.data_dir / "app.sqlite3")
    db.prune()
    last_prune = [now()]
    prune_lock = threading.Lock()
    signing_key_file = settings.data_dir / "media-signing.key"
    if settings.media_signing_key:
        media_signing_key = settings.media_signing_key
    elif settings.dev_login:
        if not signing_key_file.is_file():
            signing_key_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
            try:
                os.chmod(signing_key_file, 0o600)
            except OSError:
                pass
        media_signing_key = signing_key_file.read_text(encoding="utf-8")
    else:
        raise ValueError("缺少 MEDIA_SIGNING_KEY")
    signer = URLSafeTimedSerializer(media_signing_key, salt="media-v1")
    parse = parser_fn or (lambda link: call_parser(link, settings))
    admin_build = ROOT / "admin" / "dist"
    login_attempts = {}

    @app.before_request
    def prune_expired_data():
        if now() - last_prune[0] > 86400 and prune_lock.acquire(blocking=False):
            try:
                if now() - last_prune[0] > 86400:
                    db.prune()
                    last_prune[0] = now()
            finally:
                prune_lock.release()

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        return response

    def json_body():
        body = request.get_json(silent=True)
        return body if isinstance(body, dict) else {}

    def user_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            if not authorization.startswith("Bearer ") or len(authorization) > 300:
                return failure("请先登录", 401)
            with db.connect() as conn:
                user = conn.execute("SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.token_hash=? AND sessions.expires_at>?", (digest(authorization[7:]), now())).fetchone()
            if not user:
                return failure("登录已过期，请重新登录", 401)
            if user["disabled"]:
                return failure("此账号已停用", 403)
            g.user_id = user["id"]
            return fn(*args, **kwargs)
        return wrapped

    def admin_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            token = request.cookies.get("admin_session", "")
            if not token:
                return failure("请登录管理后台", 401)
            with db.connect() as conn:
                session = conn.execute("SELECT * FROM admin_sessions WHERE token_hash=? AND expires_at>?", (digest(token), now())).fetchone()
            if not session:
                return failure("管理登录已过期", 401)
            if request.method not in ("GET", "HEAD", "OPTIONS") and digest(request.headers.get("X-CSRF-Token", "")) != session["csrf_hash"]:
                return failure("请求校验失败，请刷新后台", 403)
            g.csrf = request.headers.get("X-CSRF-Token", "")
            return fn(*args, **kwargs)
        return wrapped

    def public_result(result, history_id, sign=True):
        if result.get("type") not in ("video", "image_album") or not isinstance(result.get("content"), list) or not 1 <= len(result["content"]) <= 100 or (result.get("type") == "video" and len(result["content"]) != 1):
            raise ParseError("解析结果格式不受支持")
        if not isinstance(result.get("aweme_id"), str) or not result["aweme_id"].isdigit() or len(result["aweme_id"]) > 32:
            raise ParseError("解析结果缺少作品 ID")
        if not isinstance(result.get("title"), str) or len(result["title"]) > 200:
            raise ParseError("解析结果标题格式错误")
        items = []
        for index, item in enumerate(result["content"]):
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                raise ParseError("解析结果中的媒体格式有误")
            output = {}
            if result["type"] == "video" and (index != 0 or "video" in item):
                raise ParseError("视频作品格式不受支持")
            fields = (("url", "video" if result["type"] == "video" else "image"), ("video", "video"), ("thumbnail", "image"))
            for field, kind in fields:
                if field in item:
                    url = item[field]
                    if not isinstance(url, str) or len(url) > 4096:
                        raise ParseError("解析结果包含过长或无效的媒体地址")
                    if not allowed_url(url, settings.media_allowed_hosts):
                        raise ParseError("解析结果包含不受支持的媒体域名")
                    output[field] = "/api/media/" + signer.dumps({"url": url, "kind": kind, "user": g.user_id, "history": history_id, "index": index}) + (".mp4" if kind == "video" else ".jpg") if sign else ""
            items.append(output)
        return {"id": history_id, "aweme_id": result["aweme_id"], "title": result["title"], "type": result["type"], "content": items}

    def parse_link(link, history_id=None):
        result = parse(link)
        if not isinstance(result, dict):
            raise ParseError("解析结果格式错误")
        # 成功前先检查全部媒体，避免写入无法正常打开的记录
        public_result(result, history_id or 0, sign=False)
        with db.connect() as conn:
            if history_id is None:
                cursor = conn.execute("INSERT INTO history(user_id,share_url,aweme_id,title,kind,item_count,created_at) VALUES(?,?,?,?,?,?,?)", (g.user_id, link, result["aweme_id"], result["title"], result["type"], len(result["content"]), now()))
                history_id = cursor.lastrowid
            else:
                conn.execute("UPDATE history SET aweme_id=?, title=?, kind=?, item_count=? WHERE id=? AND user_id=?", (result["aweme_id"], result["title"], result["type"], len(result["content"]), history_id, g.user_id))
            conn.execute("INSERT INTO parse_events(user_id,aweme_id,success,message,created_at) VALUES(?,?,1,?,?)", (g.user_id, result["aweme_id"], "解析成功", now()))
        # 令牌须绑定已创建的实际记录号
        return public_result(result, history_id)

    @app.errorhandler(413)
    def too_large(_):
        return failure("请求内容过大", 413)

    @app.post("/api/auth/wechat")
    def wechat_login():
        code = json_body().get("code", "")
        if not isinstance(code, str) or len(code) > 256 or not code:
            return failure("缺少微信登录凭证")
        if settings.dev_login and code == "dev-test":
            openid = "local-development-user"
        else:
            if settings.dev_login and (not settings.wx_appid or not settings.wx_secret):
                return failure("本地调试请使用测试登录")
            try:
                response = requests.get("https://api.weixin.qq.com/sns/jscode2session", params={"appid": settings.wx_appid, "secret": settings.wx_secret, "js_code": code, "grant_type": "authorization_code"}, timeout=(5, 10))
                response.raise_for_status()
                data = response.json()
                openid = data.get("openid")
            except (requests.RequestException, ValueError):
                return failure("微信登录服务不可用", 502)
            if not isinstance(openid, str) or not openid or data.get("errcode"):
                return failure("微信登录失败，请重试", 401)
        token = secrets.token_urlsafe(32)
        with db.connect() as conn:
            user = conn.execute("SELECT id,disabled FROM users WHERE openid=?", (openid,)).fetchone()
            if user and user["disabled"]:
                return failure("此账号已停用", 403)
            conn.execute("INSERT INTO users(openid,created_at,last_login_at) VALUES(?,?,?) ON CONFLICT(openid) DO UPDATE SET last_login_at=excluded.last_login_at", (openid, now(), now()))
            user = conn.execute("SELECT id FROM users WHERE openid=?", (openid,)).fetchone()
            conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (digest(token), user["id"], now() + 30 * 86400))
        return jsonify({"token": token, "user": {"id": user["id"]}})

    @app.get("/api/me")
    @user_required
    def me():
        with db.connect() as conn:
            user = conn.execute("SELECT id,created_at,last_login_at FROM users WHERE id=?", (g.user_id,)).fetchone()
        return jsonify({"user": dict(user)})

    @app.delete("/api/me")
    @user_required
    def erase_me():
        with db.connect() as conn:
            conn.execute("DELETE FROM users WHERE id=?", (g.user_id,))
        return jsonify({"ok": True})

    @app.post("/api/parse")
    @user_required
    def parse_work():
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM parse_events WHERE user_id=? AND created_at>?", (g.user_id, now() - 600)).fetchone()[0]
        if count >= 30:
            return failure("操作太频繁，请稍后再试", 429)
        try:
            link = extract_share_link(json_body().get("text", ""))
            return jsonify(parse_link(link))
        except (ParseError, KeyError, TypeError, ValueError) as exc:
            with db.connect() as conn:
                conn.execute("INSERT INTO parse_events(user_id,aweme_id,success,message,created_at) VALUES(?,NULL,0,?,?)", (g.user_id, str(exc)[:120], now()))
            return failure(str(exc), 422)

    @app.get("/api/history")
    @user_required
    def history():
        with db.connect() as conn:
            rows = conn.execute("SELECT id,aweme_id,title,kind,item_count,created_at FROM history WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 30", (g.user_id,)).fetchall()
        return jsonify({"items": [dict(row) for row in rows]})

    @app.post("/api/history/<int:history_id>/refresh")
    @user_required
    def refresh(history_id):
        with db.connect() as conn:
            row = conn.execute("SELECT share_url FROM history WHERE id=? AND user_id=?", (history_id, g.user_id)).fetchone()
            count = conn.execute("SELECT COUNT(*) FROM parse_events WHERE user_id=? AND created_at>?", (g.user_id, now() - 600)).fetchone()[0]
        if not row:
            return failure("记录不存在或已过期", 404)
        if count >= 30:
            return failure("操作太频繁，请稍后再试", 429)
        try:
            return jsonify(parse_link(row["share_url"], history_id))
        except (ParseError, KeyError, TypeError, ValueError) as exc:
            with db.connect() as conn:
                conn.execute("INSERT INTO parse_events(user_id,aweme_id,success,message,created_at) VALUES(?,?,0,?,?)", (g.user_id, None, str(exc)[:120], now()))
            return failure(str(exc), 422)

    @app.post("/api/saves")
    @user_required
    def save_event():
        body = json_body()
        history_id = body.get("history_id")
        index = body.get("item_index")
        kind = body.get("media_kind")
        success = body.get("success")
        if type(history_id) is not int or type(index) is not int or index < 0 or kind not in ("image", "video") or type(success) is not bool:
            return failure("保存记录参数错误")
        with db.connect() as conn:
            row = conn.execute("SELECT id,item_count,kind FROM history WHERE id=? AND user_id=?", (history_id, g.user_id)).fetchone()
            if not row or index >= row["item_count"] or (row["kind"] == "video" and kind != "video"):
                return failure("作品记录不存在", 404)
            message = str(body.get("message") or "")[:120]
            conn.execute("INSERT INTO save_events(user_id,history_id,item_index,media_kind,success,message,created_at) VALUES(?,?,?,?,?,?,?)", (g.user_id, history_id, index, kind, int(success), message, now()))
        return jsonify({"ok": True})

    @app.get("/api/media/<token>")
    def media(token):
        if len(token) > 6000:
            return failure("媒体令牌错误", 400)
        if not (token.endswith(".jpg") or token.endswith(".mp4")):
            return failure("媒体格式错误", 400)
        suffix = token.rsplit(".", 1)[1]
        try:
            payload = signer.loads(token.rsplit(".", 1)[0], max_age=settings.media_token_ttl)
        except (BadSignature, SignatureExpired):
            return failure("媒体链接已失效，请重新解析", 410)
        if not isinstance(payload, dict) or payload.get("kind") not in ("image", "video") or (suffix == "jpg") != (payload.get("kind") == "image") or not allowed_url(payload.get("url"), settings.media_allowed_hosts) or type(payload.get("index")) is not int or payload["index"] < 0:
            return failure("媒体令牌错误", 400)
        with db.connect() as conn:
            owner = conn.execute("SELECT users.disabled,history.item_count FROM history JOIN users ON users.id=history.user_id WHERE history.id=? AND history.user_id=?", (payload.get("history"), payload.get("user"))).fetchone()
        if not owner or owner["disabled"] or payload["index"] >= owner["item_count"]:
            return failure("媒体记录不可用", 403)
        try:
            if payload["kind"] == "image":
                return image_response(payload["url"], settings)
            return video_response(payload["url"], settings, request.headers.get("Range"))
        except MediaError as exc:
            return failure(str(exc), 502)

    @app.post("/admin/api/login")
    def admin_login():
        ip = request.remote_addr or "unknown"
        attempts = [t for t in login_attempts.get(ip, []) if t > now() - 900]
        if len(attempts) >= 5:
            return failure("尝试次数过多，请 15 分钟后再试", 429)
        body = json_body()
        if body.get("username") != "admin" or not settings.admin_password_hash or not check_hash(str(body.get("password", "")), settings.admin_password_hash):
            attempts.append(now())
            login_attempts[ip] = attempts
            return failure("账号或密码错误", 401)
        login_attempts.pop(ip, None)
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with db.connect() as conn:
            conn.execute("INSERT INTO admin_sessions(token_hash,csrf_hash,expires_at) VALUES(?,?,?)", (digest(token), digest(csrf), now() + 8 * 3600))
        response = jsonify({"csrf": csrf})
        response.set_cookie("admin_session", token, httponly=True, secure=settings.cookie_secure, samesite="Strict", path="/admin", max_age=8 * 3600)
        response.set_cookie("admin_csrf", csrf, httponly=False, secure=settings.cookie_secure, samesite="Strict", path="/admin", max_age=8 * 3600)
        return response

    @app.get("/admin/api/session")
    @admin_required
    def admin_session():
        return jsonify({"ok": True})

    @app.post("/admin/api/logout")
    @admin_required
    def admin_logout():
        with db.connect() as conn:
            conn.execute("DELETE FROM admin_sessions WHERE token_hash=?", (digest(request.cookies["admin_session"]),))
        response = jsonify({"ok": True})
        response.delete_cookie("admin_session", path="/admin")
        response.delete_cookie("admin_csrf", path="/admin")
        return response

    @app.get("/admin/api/overview")
    @admin_required
    def overview():
        with db.connect() as conn:
            values = {}
            start_of_day_china = (now() + 28800) // 86400 * 86400 - 28800
            for key, sql in (
                ("users", "SELECT COUNT(*) FROM users"),
                ("today_logins", "SELECT COUNT(*) FROM users WHERE last_login_at>=?"),
                ("today_parses", "SELECT COUNT(*) FROM parse_events WHERE created_at>=?"),
                ("today_parse_success", "SELECT COUNT(*) FROM parse_events WHERE success=1 AND created_at>=?"),
                ("today_saves", "SELECT COUNT(*) FROM save_events WHERE success=1 AND created_at>=?"),
            ):
                args = () if key == "users" else (start_of_day_china,)
                values[key] = conn.execute(sql, args).fetchone()[0]
        return jsonify(values)

    @app.get("/admin/api/users")
    @admin_required
    def admin_users():
        search = request.args.get("q", "")[:40]
        with db.connect() as conn:
            if search.isdigit():
                rows = conn.execute("SELECT id,created_at,last_login_at,disabled FROM users WHERE id=?", (int(search),)).fetchall()
            else:
                rows = conn.execute("SELECT id,created_at,last_login_at,disabled FROM users ORDER BY id DESC LIMIT 100").fetchall()
        return jsonify({"items": [dict(row) for row in rows]})

    @app.post("/admin/api/users/<int:user_id>/status")
    @admin_required
    def admin_user_status(user_id):
        disabled = json_body().get("disabled")
        if type(disabled) is not bool:
            return failure("状态参数错误")
        with db.connect() as conn:
            updated = conn.execute("UPDATE users SET disabled=? WHERE id=?", (int(disabled), user_id)).rowcount
            if disabled:
                conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return jsonify({"ok": bool(updated)}) if updated else failure("用户不存在", 404)

    @app.get("/admin/api/events")
    @admin_required
    def admin_events():
        kind = request.args.get("kind", "parse")
        if kind not in ("parse", "save"):
            return failure("记录类型错误")
        user = request.args.get("user_id", "")
        if user and not user.isdigit():
            return failure("用户 ID 格式错误")
        table = "parse_events" if kind == "parse" else "save_events"
        where = "WHERE user_id=?" if user else ""
        with db.connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table} {where} ORDER BY id DESC LIMIT 100", (int(user),) if user else ()).fetchall()
        return jsonify({"items": [dict(row) for row in rows]})

    @app.get("/admin/")
    @app.get("/admin/<path:filename>")
    def admin_static(filename="index.html"):
        if not admin_build.is_dir():
            return failure("请先构建管理后台：cd admin && npm run build", 503)
        if not filename.startswith("assets/") and filename != "index.html":
            return failure("页面不存在", 404)
        if (admin_build / filename).is_file():
            return send_from_directory(admin_build, filename)
        return failure("页面不存在", 404)

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    app.extensions["project_db"] = db
    app.extensions["media_signer"] = signer
    return app
