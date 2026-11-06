# 保存助手：Vue 微信小程序 + 独立管理后台

第一版已实现：微信登录和内部用户 ID、粘贴分享文案解析、视频/图集/带视频的实况图片识别、预览、保存到相册、最近记录、账号注销；独立网页管理后台提供用户统计、解析与保存记录、停用/启用用户。小程序端没有管理入口。解析算法由你现有的 API 提供，本项目只负责调用和展示。

目录：`miniprogram/` 是 uni-app Vue 3 小程序；`admin/` 是 Vue 3 + Vite 管理页；`server/` 是 Flask + SQLite 服务。管理页打包后由同一个 Flask 服务托管，无需单独部署 Node 服务。

## 本地运行

准备 Python 3.9+、Node.js 18+、微信开发者工具：

```powershell
python -m pip install -r server/requirements.txt
Copy-Item server/.env.example server/.env
python -m server.hash_password
```

把密码摘要填入 `server/.env` 的 `ADMIN_PASSWORD_HASH`，把你的解析 API 地址填入 `PARSER_API_URL`，然后：

```powershell
cd admin
npm ci
npm run build
cd ..
python -m server
```

打开 `http://127.0.0.1:8000/admin/`，使用 `admin` 与设定的密码登录。后台初始密码不会自动生成，也没有默认密码。

小程序编译：

```powershell
cd miniprogram
npm ci
npm run build:mp-weixin
```

将 `miniprogram/dist/build/mp-weixin/` 导入微信开发者工具。本地模拟器用 `server/.env` 中的 `DEV_LOGIN=true` 与 `miniprogram/src/config.js` 中的 `DEV_LOGIN=true`；开发者工具本地调试需临时关闭合法域名校验。后端的解析 API 地址必须先配置，否则解析会报“解析服务尚未配置”。正式上传前保持或恢复开发者工具中的合法域名校验。

## 解析 API 接入

默认向 `PARSER_API_URL` 发送 `POST` JSON `{"url":"https://v.douyin.com/..."}`；支持用 `PARSER_API_METHOD=GET` 切换为 GET 查询参数 `url`。如需 API Key，配置 `PARSER_API_KEY`、`PARSER_AUTH_HEADER` 和 `PARSER_AUTH_PREFIX`；默认发送 `Authorization: Bearer <密钥>`。如果现有 API 的参数、请求格式、认证方式不同，修改 [解析适配器](server/parser.py) 的 `call_parser()`。接口响应应符合给出的示例结构：`status`、`aweme_id`、`title`、`type`、`content`；实况内容的图片项含 `video` 字段。

媒体 URL 仅在解析时返回为服务端签发的短时访问链接，数据库保留原始分享链接用于历史记录重新解析，不持久存储签名媒体 URL。图集 WebP 在服务端转为 JPEG，视频从服务端按需转发并支持 HTTP Range。实况照片第一版分别保存静态图片和 MP4，暂不合成为手机相册原生实况照片。媒体允许的 CDN 后缀配置在 `MEDIA_ALLOWED_HOSTS`；新的 CDN 域名要确认后再加入。

## 单机部署

可用 [Dockerfile](Dockerfile) 与 [compose.yaml](compose.yaml) 构建后端和后台，SQLite 数据挂载到 `server/data/`。给前端加 Nginx/Caddy HTTPS 反向代理，指向 `127.0.0.1:8000`；管理后台访问路径为 `/admin/`。示例配置不能直接公开上线，部署前：

1. `server/.env` 设置 `DEV_LOGIN=false`、微信小程序 `WX_APPID` 和 `WX_SECRET`、真正的 `PARSER_API_URL`、`ADMIN_PASSWORD_HASH`、`COOKIE_SECURE=true`，以及随机 32 位以上的 `MEDIA_SIGNING_KEY`（例如 `python -c "import secrets;print(secrets.token_urlsafe(48))"`）。不要提交 `.env`。
2. `miniprogram/src/config.js` 改为公网 HTTPS 域名、`DEV_LOGIN=false`；在 `miniprogram/src/manifest.json` 填入真实微信小程序 AppID，重新构建。微信后台至少配置该域名为 request 和 download 合法域名；媒体代理统一走你的域名。
3. 检查小程序类目、备案和个人主体适用规则；配置隐私保护指引，说明微信标识、分享链接、解析/保存记录的用途以及保存 30 天。对照你现有 API 的使用规则和内容授权要求。
4. 安卓、iPhone 真机分别验证视频、图集、实况视频、相册权限和过期链接刷新。带宽与媒体大小上限分别通过 `MAX_VIDEO_BYTES` 和 `MAX_IMAGE_BYTES` 控制。SQLite 数据目录需备份。

本地 `DEV_LOGIN=true` 仅能监听本机，模拟器中使用统一测试身份；不能部署到公网。用户登录凭证 30 天有效，记录保留 30 天并在服务器有请求时每日清理；可在“我的”主动注销以立即删除数据。后台今日统计按北京时间计算。后台只查询内部用户 ID，不显示 OpenID；保存记录表示客户端保存接口的回报。后台登录试错限制是单进程内存计数，正式环境还应在 HTTPS 反向代理处为 `/admin/api/login` 配置请求限速。

## 验证

```powershell
python -m unittest discover -s tests -v
```

小程序与管理页的构建分别使用 `npm run build:mp-weixin`、`npm run build`。接入真实 API 后需另做真机验收；代码仓库未包含真实微信密钥、解析 API 地址或真实 API 响应回放。
