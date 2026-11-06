import io
import tempfile
import unittest
import os
from types import SimpleNamespace
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from server.app import create_app
from server.hash_password import make_hash
from server.media import MediaError, allowed_url, resolve_public_ip
from server.parser import call_parser
from server.settings import load_settings


def example_parser(_):
    return {
        "status": "success", "aweme_id": "7608287139733812899", "title": "测试实况照片", "type": "image_album",
        "content": [{"url": "https://p3.douyinpic.com/test.webp", "video": "https://v3.zjcdn.com/test.mp4", "thumbnail": "https://p3.douyinpic.com/cover.jpg"}],
    }


class MockMedia:
    status_code = 200
    headers = {"Content-Length": "4096", "Content-Type": "image/webp"}

    def __init__(self, data):
        self.data = data
        self.headers = {"Content-Length": str(len(data)), "Content-Type": "image/webp"}

    def iter_content(self, _):
        yield self.data

    def close(self):
        pass


class MockVideo(MockMedia):
    status_code = 206

    def __init__(self):
        super().__init__(b"MP4!")
        self.headers = {"Content-Length": "4", "Content-Type": "video/mp4", "Content-Range": "bytes 0-3/4"}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {"DEV_LOGIN": "true", "HOST": "127.0.0.1"}):
            settings = load_settings()
        settings = replace(settings, data_dir=Path(self.temp.name), dev_login=True, host="127.0.0.1", cookie_secure=False, admin_password_hash=make_hash("a-long-test-password"), media_signing_key="test-signing-secret")
        self.app_settings = settings
        self.app = create_app(settings, parser_fn=example_parser)
        self.client = self.app.test_client()
        self.login = self.client.post("/api/auth/wechat", json={"code": "dev-test"}).json
        self.headers = {"Authorization": "Bearer " + self.login["token"]}

    def test_login_parse_history_refresh_and_save_record(self):
        parsed = self.client.post("/api/parse", json={"text": "分享 https://v.douyin.com/abc/"}, headers=self.headers)
        self.assertEqual(parsed.status_code, 200)
        result = parsed.json
        self.assertEqual(result["type"], "image_album")
        self.assertTrue(result["content"][0]["video"].endswith(".mp4"))
        self.assertTrue(result["content"][0]["url"].endswith(".jpg"))
        history = self.client.get("/api/history", headers=self.headers).json["items"]
        self.assertEqual(len(history), 1)
        self.assertNotIn("share_url", history[0])
        self.assertNotIn("openid", str(history[0]))
        fresh = self.client.post(f"/api/history/{result['id']}/refresh", headers=self.headers)
        self.assertEqual(fresh.status_code, 200)
        self.assertEqual(fresh.json["id"], result["id"])
        save = self.client.post("/api/saves", headers=self.headers, json={"history_id": result["id"], "item_index": 0, "media_kind": "video", "success": True})
        self.assertEqual(save.status_code, 200)
        self.assertEqual(self.client.post("/api/saves", headers=self.headers, json={"history_id": result["id"], "item_index": 1, "media_kind": "video", "success": True}).status_code, 404)

    def test_media_signed_token_image_conversion_and_tampering(self):
        result = self.client.post("/api/parse", json={"text": "https://v.douyin.com/abc/"}, headers=self.headers).json
        source = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(source, "WEBP")
        with patch("server.media.open_media", return_value=MockMedia(source.getvalue())):
            image = self.client.get(result["content"][0]["url"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/jpeg")
        self.assertTrue(image.data.startswith(b"\xff\xd8"))
        self.assertEqual(self.client.get(result["content"][0]["url"] + "x").status_code, 400)
        self.assertEqual(self.client.get(result["content"][0]["url"].replace(".jpg", ".mp4")).status_code, 400)

    def test_video_range_proxy(self):
        result = self.client.post("/api/parse", json={"text": "https://v.douyin.com/abc/"}, headers=self.headers).json
        with patch("server.media.open_media", return_value=MockVideo()) as upstream:
            response = self.client.get(result["content"][0]["video"], headers={"Range": "bytes=0-3"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.headers["Content-Range"], "bytes 0-3/4")
            self.assertEqual(response.data, b"MP4!")
            upstream.assert_called_once()
            self.assertEqual(upstream.call_args.args[2], "bytes=0-3")

    def test_admin_permissions_csrf_and_deletion(self):
        self.assertEqual(self.client.get("/admin/api/users").status_code, 401)
        signin = self.client.post("/admin/api/login", json={"username": "admin", "password": "a-long-test-password"})
        self.assertEqual(signin.status_code, 200)
        self.assertEqual(self.client.get("/admin/api/overview").json["users"], 1)
        user_id = self.login["user"]["id"]
        url = f"/admin/api/users/{user_id}/status"
        self.assertEqual(self.client.post(url, json={"disabled": True}).status_code, 403)
        self.assertEqual(self.client.post(url, json={"disabled": True}, headers={"X-CSRF-Token": signin.json["csrf"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/me", headers=self.headers).status_code, 401)

    def test_account_deletion_removes_personal_records(self):
        self.client.post("/api/parse", json={"text": "https://v.douyin.com/abc/"}, headers=self.headers)
        self.assertEqual(self.client.delete("/api/me", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get("/api/history", headers=self.headers).status_code, 401)
        with self.app.extensions["project_db"].connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM parse_events").fetchone()[0], 0)

    def test_invalid_input_and_media_domain(self):
        self.assertEqual(self.client.post("/api/parse", json={"text": "https://evil.example/x"}, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post("/api/parse", json={"text": "http://v.douyin.com/x"}, headers=self.headers).status_code, 422)
        self.assertFalse(allowed_url("https://evil.example/?next=douyinpic.com", ("douyinpic.com",)))
        self.assertFalse(allowed_url("https://evil-douyinpic.com/x", ("douyinpic.com",)))
        self.assertFalse(allowed_url("https://p3.douyinpic.com:444/x", ("douyinpic.com",)))
        self.assertTrue(allowed_url("https://p3.douyinpic.com/test.webp", ("douyinpic.com",)))
        with patch("server.media.socket.getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(MediaError):
                resolve_public_ip("p3.douyinpic.com")

    def test_parser_adapter_auth_and_sample_result(self):
        with patch.dict(os.environ, {"DEV_LOGIN": "true", "HOST": "127.0.0.1"}):
            settings = load_settings()
        settings = replace(settings, parser_api_url="https://api.example.test/parse", parser_api_key="secret", parser_auth_prefix="Bearer", parser_auth_header="Authorization", parser_api_method="POST")
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: example_parser(None))
        with patch("server.parser.requests.post", return_value=response) as client:
            result = call_parser("https://v.douyin.com/abc/", settings)
        self.assertEqual(client.call_args.kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(client.call_args.kwargs["json"], {"url": "https://v.douyin.com/abc/"})
        self.assertEqual(result["content"][0]["video"], "https://v3.zjcdn.com/test.mp4")

    def test_unauthorized_media_host_is_not_saved(self):
        def unsafe(_):
            result = example_parser(None)
            result["content"][0]["url"] = "https://private.example.test/image.webp"
            return result
        app = create_app(replace(self.app_settings, data_dir=Path(self.temp.name) / "unsafe"), parser_fn=unsafe)
        client = app.test_client()
        token = client.post("/api/auth/wechat", json={"code": "dev-test"}).json["token"]
        response = client.post("/api/parse", json={"text": "https://v.douyin.com/abc/"}, headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(client.get("/api/history", headers={"Authorization": "Bearer " + token}).json["items"], [])


if __name__ == "__main__":
    unittest.main()
