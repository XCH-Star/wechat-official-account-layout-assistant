from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


TOKEN_API = "https://api.weixin.qq.com/cgi-bin/token"
UPLOAD_IMG_API = "https://api.weixin.qq.com/cgi-bin/media/uploadimg"
ADD_MATERIAL_API = "https://api.weixin.qq.com/cgi-bin/material/add_material"
ADD_DRAFT_API = "https://api.weixin.qq.com/cgi-bin/draft/add"
DRAFT_GET_API = "https://api.weixin.qq.com/cgi-bin/draft/get"
DRAFT_UPDATE_API = "https://api.weixin.qq.com/cgi-bin/draft/update"

ENHANCED_TEMPLATE_NAME = "wechat_article_template_enhanced.html"
DEFAULT_TEMPLATE_NAME = "wechat_article_template.html"

ERRCODE_HINTS = {
    40001: "Invalid credential. Check AppID/AppSecret or refresh the access token.",
    40004: "Invalid media type. The uploaded cover must be an image material.",
    40007: "Invalid media_id. Check the draft media_id or thumb_media_id.",
    40013: "Invalid AppID. Check WECHAT_APP_ID.",
    41001: "Missing access_token.",
    45009: "API call quota exceeded. Try later or check quota limits.",
    47001: "Invalid JSON payload. Check generated article fields and HTML size.",
    48001: "API unauthorized. Check Official Account API permissions.",
    40164: "Invalid IP. Add the current public IP to the WeChat Official Account IP whitelist.",
}


class WeChatApiError(RuntimeError):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_credentials(env_file: Path) -> tuple[str, str]:
    values = read_env_file(env_file)
    merged = {**values, **os.environ}
    app_id = merged.get("WECHAT_APP_ID") or merged.get("WECHAT_APPID")
    app_secret = merged.get("WECHAT_APP_SECRET") or merged.get("WECHAT_APPSECRET")
    if not app_id or not app_secret:
        raise RuntimeError("WECHAT_APP_ID and WECHAT_APP_SECRET must be set in the env file or environment.")
    return app_id, app_secret


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required package file is missing: {path}")
    return path.resolve()


def explain_errcode(errcode: Any) -> str:
    try:
        return ERRCODE_HINTS.get(int(errcode), "")
    except (TypeError, ValueError):
        return ""


def wechat_error_if_any(payload: dict[str, Any], context: str) -> None:
    errcode = payload.get("errcode")
    if errcode not in (None, 0, "0"):
        hint = explain_errcode(errcode)
        details = f"{context} failed: errcode={errcode} errmsg={payload.get('errmsg', '')}"
        if hint:
            details = f"{details} hint={hint}"
        raise WeChatApiError(details)


def http_json_get(url: str, params: dict[str, str], context: str) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full_url, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    wechat_error_if_any(data, context)
    return data


def http_json_post(url: str, params: dict[str, str], payload: dict[str, Any], context: str) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        full_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    wechat_error_if_any(data, context)
    return data


def multipart_upload(url: str, image_path: Path, context: str) -> dict[str, Any]:
    boundary = f"----CodexWechatBoundary{uuid.uuid4().hex}"
    filename = image_path.name
    content_type = mimetypes.guess_type(filename)[0] or "image/png"
    file_bytes = image_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'.encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
    wechat_error_if_any(data, context)
    return data


def wechat_safe_html(html: str) -> str:
    html = re.sub(r"(?is)<li\b[^>]*>\s*(?:&nbsp;|<br\s*/?>)?\s*</li>", "", html)
    html = re.sub(r"(?is)(<(?:ul|ol)\b[^>]*>)\s+(<li\b)", r"\1\2", html)
    html = re.sub(r"(?is)(</li>)\s+(<li\b)", r"\1\2", html)
    html = re.sub(r"(?is)(</li>)\s+(</(?:ul|ol)>)", r"\1\2", html)
    return html


def resolve_template_path(package_dir: Path, template_name: str | None) -> Path:
    if template_name:
        return require_file(package_dir / template_name)
    enhanced_template = package_dir / ENHANCED_TEMPLATE_NAME
    if enhanced_template.exists():
        return enhanced_template.resolve()
    return require_file(package_dir / DEFAULT_TEMPLATE_NAME)


def normalize_content_images(config: dict[str, Any]) -> list[dict[str, str]]:
    if "content_images" in config:
        content_images = [
            {"placeholder": item["placeholder"], "file": item.get("file") or item.get("path", "")}
            for item in config["content_images"]
        ]
    elif isinstance(config.get("images"), list):
        content_images = [
            {"placeholder": item["placeholder"], "file": item["path"]}
            for item in config["images"]
        ]
    elif isinstance(config.get("image_placeholders"), dict):
        content_images = [
            {"placeholder": placeholder, "file": file_path}
            for placeholder, file_path in config["image_placeholders"].items()
        ]
    else:
        raise RuntimeError("article_config.json must define content_images, images list, or image_placeholders.")

    for item in content_images:
        if not item.get("placeholder") or not item.get("file"):
            raise RuntimeError(f"Invalid image config item: {item}")
    return content_images


def resolve_cover_file(config: dict[str, Any], content_images: list[dict[str, str]]) -> str:
    cover_image = config.get("cover_image")
    if cover_image:
        return str(cover_image)
    if isinstance(config.get("images"), dict):
        cover_from_dict = config["images"].get("cover")
        if cover_from_dict:
            return str(cover_from_dict)
    return next(
        (item["file"] for item in content_images if item["placeholder"] == "{{IMG_COVER_URL}}"),
        content_images[0]["file"],
    )


def draft_flag(config: dict[str, Any], key: str, default: int = 0) -> int:
    draft_config = config.get("wechat_draft", {})
    return int(config.get(key, draft_config.get(key, default)))


def read_package(package_dir: Path, template_name: str | None) -> dict[str, Any]:
    package_dir = package_dir.resolve()
    config = json.loads(require_file(package_dir / "article_config.json").read_text(encoding="utf-8"))
    template_path = resolve_template_path(package_dir, template_name)
    content_images = normalize_content_images(config)
    cover_file = resolve_cover_file(config, content_images)

    image_files = [package_dir / item["file"] for item in content_images]
    cover_path = package_dir / cover_file
    if cover_path not in image_files:
        image_files.insert(0, cover_path)

    for image_path in image_files:
        require_file(image_path)

    html = template_path.read_text(encoding="utf-8")
    missing_placeholders = [item["placeholder"] for item in content_images if item["placeholder"] not in html]
    if missing_placeholders:
        raise RuntimeError(f"Template is missing image placeholders: {missing_placeholders}")

    return {
        "package_dir": package_dir,
        "config": config,
        "template_path": template_path,
        "content_images": content_images,
        "cover_file": cover_file,
        "image_files": image_files,
    }


def get_access_token(app_id: str, app_secret: str) -> str:
    token_payload = http_json_get(
        TOKEN_API,
        {"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
        "get access_token",
    )
    return token_payload["access_token"]


def upload_inline_images(access_token: str, package: dict[str, Any]) -> tuple[str, dict[str, str]]:
    package_dir: Path = package["package_dir"]
    template_path: Path = package["template_path"]
    content_images: list[dict[str, str]] = package["content_images"]

    html = template_path.read_text(encoding="utf-8")
    uploaded_urls: dict[str, str] = {}
    upload_url = f"{UPLOAD_IMG_API}?{urllib.parse.urlencode({'access_token': access_token})}"
    for item in content_images:
        placeholder = item["placeholder"]
        image_path = require_file(package_dir / item["file"])
        result = multipart_upload(upload_url, image_path, f"upload inline image {image_path.name}")
        image_url = result.get("url")
        if not image_url:
            raise RuntimeError(f"Inline image upload did not return url: {result}")
        html = html.replace(placeholder, image_url)
        uploaded_urls[placeholder] = image_url

    for placeholder in [item["placeholder"] for item in content_images]:
        if placeholder in html:
            raise RuntimeError(f"Image placeholder was not replaced: {placeholder}")
    return wechat_safe_html(html), uploaded_urls


def upload_cover_material(access_token: str, package: dict[str, Any]) -> str:
    package_dir: Path = package["package_dir"]
    cover_path = require_file(package_dir / package["cover_file"])
    material_url = f"{ADD_MATERIAL_API}?{urllib.parse.urlencode({'access_token': access_token, 'type': 'image'})}"
    result = multipart_upload(material_url, cover_path, "upload cover permanent material")
    thumb_media_id = result.get("media_id")
    if not thumb_media_id:
        raise RuntimeError(f"Cover material upload did not return media_id: {result}")
    return thumb_media_id


def build_article(config: dict[str, Any], html: str, thumb_media_id: str) -> dict[str, Any]:
    return {
        "title": config["title"],
        "author": config["author"],
        "digest": config["digest"],
        "content": html,
        "content_source_url": config.get("content_source_url", ""),
        "thumb_media_id": thumb_media_id,
        "show_cover_pic": draft_flag(config, "show_cover_pic", 0),
        "need_open_comment": draft_flag(config, "need_open_comment", 0),
        "only_fans_can_comment": draft_flag(config, "only_fans_can_comment", 0),
    }


def create_draft(args: argparse.Namespace) -> dict[str, Any]:
    package = read_package(Path(args.package_dir), args.template)
    app_id, app_secret = load_credentials(Path(args.env_file).resolve())
    access_token = get_access_token(app_id, app_secret)
    html, uploaded_urls = upload_inline_images(access_token, package)
    thumb_media_id = upload_cover_material(access_token, package)
    article = build_article(package["config"], html, thumb_media_id)
    result = http_json_post(ADD_DRAFT_API, {"access_token": access_token}, {"articles": [article]}, "create draft")
    return {
        "ok": True,
        "action": "create",
        "draft_media_id": result.get("media_id"),
        "template": package["template_path"].name,
        "thumb_media_id": thumb_media_id,
        "inline_images": uploaded_urls,
        "wechat_result": result,
    }


def update_draft(args: argparse.Namespace) -> dict[str, Any]:
    package = read_package(Path(args.package_dir), args.template)
    app_id, app_secret = load_credentials(Path(args.env_file).resolve())
    access_token = get_access_token(app_id, app_secret)
    current = http_json_post(
        DRAFT_GET_API,
        {"access_token": access_token},
        {"media_id": args.media_id},
        "get existing draft",
    )
    current_article = current["news_item"][0]
    thumb_media_id = (
        upload_cover_material(access_token, package)
        if args.replace_cover
        else current_article["thumb_media_id"]
    )
    html, uploaded_urls = upload_inline_images(access_token, package)
    article = build_article(package["config"], html, thumb_media_id)
    result = http_json_post(
        DRAFT_UPDATE_API,
        {"access_token": access_token},
        {"media_id": args.media_id, "index": args.index, "articles": article},
        "update draft",
    )
    return {
        "ok": True,
        "action": "update",
        "draft_media_id": args.media_id,
        "template": package["template_path"].name,
        "thumb_media_id": thumb_media_id,
        "inline_images": uploaded_urls,
        "wechat_result": result,
    }


def check_package(args: argparse.Namespace) -> dict[str, Any]:
    package = read_package(Path(args.package_dir), args.template)
    return {
        "ok": True,
        "action": "check",
        "title": package["config"].get("title"),
        "template": package["template_path"].name,
        "uses_enhanced_template": package["template_path"].name == ENHANCED_TEMPLATE_NAME,
        "cover_file": package["cover_file"],
        "image_count": len(package["image_files"]),
        "images": [
            {"file": str(path), "bytes": path.stat().st_size}
            for path in package["image_files"]
        ],
        "placeholders": [item["placeholder"] for item in package["content_images"]],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or update WeChat Official Account drafts from a prepared article package."
    )
    parser.add_argument("--env-file", default=".env.wechat.local")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Validate package files and template placeholders.")
    check_parser.add_argument("--package-dir", required=True)
    check_parser.add_argument("--template", default=None)

    create_parser = subparsers.add_parser("create", help="Create a WeChat draft. Never publishes.")
    create_parser.add_argument("--package-dir", required=True)
    create_parser.add_argument("--template", default=None)

    update_parser = subparsers.add_parser("update", help="Update an existing WeChat draft. Never publishes.")
    update_parser.add_argument("--package-dir", required=True)
    update_parser.add_argument("--media-id", required=True)
    update_parser.add_argument("--template", default=None)
    update_parser.add_argument("--index", type=int, default=0)
    update_parser.add_argument("--replace-cover", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = check_package(args)
        elif args.command == "create":
            result = create_draft(args)
        elif args.command == "update":
            result = update_draft(args)
        else:
            parser.error(f"Unknown command: {args.command}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
