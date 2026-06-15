from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from typing import Any


ENHANCED_TEMPLATE_NAME = "wechat_article_template_enhanced.html"
AUTO_TEMPLATE_NAME = "wechat_article_template_auto_enhanced.html"
DEFAULT_TEMPLATE_NAME = "wechat_article_template.html"

BASE_FONT_STYLE = (
    "max-width:677px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,"
    "'Helvetica Neue','PingFang SC','Hiragino Sans GB','Microsoft YaHei',Arial,sans-serif;"
    "color:#24372c;line-height:1.9;font-size:15.5px;background:#ffffff;"
)


def _escape(text: str) -> str:
    return html_lib.escape(text.strip(), quote=True)


def _p(text: str, style: str | None = None) -> str:
    style = style or "margin:16px 0;color:#2f4035;line-height:1.92;"
    return f'<p style="{style}">{_escape(text)}</p>'


def _section_title(title: str, index: int) -> str:
    title = _escape(title)
    if index % 2:
        return (
            '<section style="margin:28px 0 14px 0;padding:16px 18px;border-radius:15px;'
            'background:#1f5c35;color:#ffffff;box-shadow:0 8px 22px rgba(31,92,53,.16);">'
            f'<p style="margin:0;font-size:13px;letter-spacing:1px;color:#d9f0df;">{index:02d} / 重点展开</p>'
            f'<p style="margin:4px 0 0 0;font-size:19px;font-weight:800;line-height:1.6;">{title}</p>'
            "</section>"
        )
    return (
        '<section style="margin:28px 0 14px 0;padding:16px 18px;border-radius:15px;'
        'background:#eaf5ec;border:1px solid #d6ead9;">'
        f'<p style="margin:0;font-size:13px;letter-spacing:1px;color:#1f5c35;">{index:02d} / 重点展开</p>'
        f'<p style="margin:4px 0 0 0;font-size:19px;font-weight:800;color:#1f5c35;line-height:1.6;">{title}</p>'
        "</section>"
    )


def _image_block(placeholder: str, caption: str = "") -> str:
    caption_html = ""
    if caption:
        caption_html = (
            f'<p style="margin:10px 0 0 0;color:#66786b;font-size:13.5px;text-align:center;">{_escape(caption)}</p>'
        )
    return (
        '<section style="margin:24px 0 18px 0;">'
        f'<img src="{placeholder}" style="width:100%;display:block;border-radius:14px;'
        'box-shadow:0 8px 24px rgba(31,92,53,.12);" alt="公众号配图" />'
        f"{caption_html}</section>"
    )


def _callout(text: str) -> str:
    return (
        '<section style="margin:22px 0;padding:15px 17px;border-left:5px solid #1f5c35;'
        'background:#f4faf5;border-radius:0 14px 14px 0;box-shadow:0 5px 16px rgba(31,92,53,.06);">'
        f'<p style="margin:0;font-size:17px;font-weight:800;color:#1f5c35;line-height:1.8;">{_escape(text)}</p>'
        "</section>"
    )


def _quote_card(text: str) -> str:
    return (
        '<section style="margin:26px 0;padding:20px;border-radius:18px;'
        'background:linear-gradient(135deg,#1f5c35 0%,#164529 100%);color:#ffffff;'
        'box-shadow:0 10px 26px rgba(31,92,53,.20);">'
        f'<p style="margin:0;font-size:18px;font-weight:800;line-height:1.9;">{_escape(text)}</p>'
        "</section>"
    )


def _interaction_card(text: str) -> str:
    return (
        '<section style="margin:26px 0 6px 0;padding:17px 18px;border-radius:16px;'
        'background:#eef8f0;border:1px solid #d7eadc;text-align:center;">'
        '<p style="margin:0;color:#1f5c35;font-size:17px;font-weight:800;">欢迎留言交流</p>'
        f'<p style="margin:9px 0 0 0;color:#39483f;line-height:1.8;">{_escape(text)}</p>'
        "</section>"
    )


def _is_interaction_text(text: str) -> bool:
    return text.startswith("欢迎") or "点赞" in text or "在看" in text or "留言" in text


def _is_quote_text(text: str) -> bool:
    return (
        "一句话" in text
        or "首先要" in text
        or "才能" in text and "；" in text
        or text.startswith("一寸土地")
    )


def _extract_markdown_tokens(article_md: str, content_images: list[dict[str, str]]) -> tuple[str, list[tuple[str, str]]]:
    lines = article_md.splitlines()
    title = ""
    tokens: list[tuple[str, str]] = []
    body_image_placeholders = [
        item["placeholder"]
        for item in content_images
        if item["placeholder"] != "{{IMG_COVER_URL}}"
    ]
    next_image_index = 0
    skip_summary = False
    skip_image_note = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            skip_summary = False
            skip_image_note = False
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            continue
        if line.startswith("【建议摘要】"):
            skip_summary = True
            continue
        if skip_summary:
            continue
        if line.startswith("【配图"):
            if "封面" not in line and next_image_index < len(body_image_placeholders):
                tokens.append(("image", body_image_placeholders[next_image_index]))
                next_image_index += 1
            skip_image_note = True
            continue
        if skip_image_note and (line.startswith("建议使用") or line.startswith("放在") or line.startswith("建议")):
            continue
        if line.startswith("## "):
            tokens.append(("h2", line[3:].strip()))
            continue
        if line.startswith("- ") or line.startswith("* "):
            tokens.append(("p", line[2:].strip()))
            continue
        tokens.append(("p", line))

    for placeholder in body_image_placeholders[next_image_index:]:
        tokens.append(("image", placeholder))
    return title, tokens


def render_auto_enhanced_template(
    package_dir: Path,
    config: dict[str, Any],
    content_images: list[dict[str, str]],
) -> str:
    article_path = package_dir / "article.md"
    if not article_path.exists():
        raise FileNotFoundError(f"Cannot auto-build enhanced template without article.md: {article_path}")
    markdown = article_path.read_text(encoding="utf-8")
    markdown_title, tokens = _extract_markdown_tokens(markdown, content_images)
    title = str(config.get("title") or markdown_title or "公众号文章")
    digest = str(config.get("digest") or "")
    author = str(config.get("author") or "GIS深度观察")
    cover_placeholder = next(
        (item["placeholder"] for item in content_images if item["placeholder"] == "{{IMG_COVER_URL}}"),
        content_images[0]["placeholder"],
    )

    parts = [
        f'<section style="{BASE_FONT_STYLE}">',
        _image_block(cover_placeholder),
        (
            '<section style="margin:18px 0 22px 0;padding:18px 18px 20px;border-radius:16px;'
            'background:linear-gradient(135deg,#eef8f0 0%,#ffffff 58%,#f7fbf4 100%);'
            'border:1px solid #d7eadc;box-shadow:0 6px 20px rgba(31,92,53,.06);">'
            '<p style="margin:0 0 10px 0;">'
            '<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
            'background:#1f5c35;color:#ffffff;font-size:13px;font-weight:700;letter-spacing:.5px;">'
            f"{_escape(author)}</span></p>"
            f'<p style="margin:0;color:#1f5c35;font-weight:800;font-size:20px;line-height:1.65;">{_escape(title)}</p>'
            f'<p style="margin:12px 0 0 0;color:#53645a;font-size:14.5px;line-height:1.85;">{_escape(digest)}</p>'
            "</section>"
        ),
    ]

    section_index = 0
    for token_type, value in tokens:
        if token_type == "h2":
            section_index += 1
            parts.append(_section_title(value, section_index))
        elif token_type == "image":
            parts.append(_image_block(value))
        elif token_type == "p":
            if _is_interaction_text(value):
                parts.append(_interaction_card(value))
            elif _is_quote_text(value) and len(value) <= 120:
                parts.append(_callout(value) if section_index == 0 else _quote_card(value))
            else:
                parts.append(_p(value))

    parts.append("</section>")
    return "\n".join(parts)


def build_auto_enhanced_template(
    package_dir: Path,
    config: dict[str, Any],
    content_images: list[dict[str, str]],
) -> Path:
    template_path = package_dir / AUTO_TEMPLATE_NAME
    html = render_auto_enhanced_template(package_dir, config, content_images)
    template_path.write_text(html, encoding="utf-8")
    return template_path.resolve()


def resolve_preferred_template_path(
    package_dir: Path,
    template_name: str | None,
    config: dict[str, Any],
    content_images: list[dict[str, str]],
) -> Path:
    if template_name:
        return (package_dir / template_name).resolve()
    enhanced_template = package_dir / ENHANCED_TEMPLATE_NAME
    if enhanced_template.exists():
        return enhanced_template.resolve()
    if (package_dir / "article.md").exists():
        return build_auto_enhanced_template(package_dir, config, content_images)
    return (package_dir / DEFAULT_TEMPLATE_NAME).resolve()


def beautify_wechat_html(html: str) -> str:
    html = re.sub(r"(?is)<p\b[^>]*>\s*(?:&nbsp;|<br\s*/?>)?\s*</p>", "", html)
    html = re.sub(r"(?is)<li\b[^>]*>\s*(?:&nbsp;|<br\s*/?>)?\s*</li>", "", html)
    html = re.sub(r"(?is)<br\s*/?>\s*<br\s*/?>", "<br/>", html)
    html = re.sub(r"(?is)<p>", '<p style="margin:16px 0;color:#2f4035;line-height:1.92;">', html)
    html = re.sub(
        r"(?is)<img(?![^>]*\bstyle=)([^>]*)>",
        r'<img\1 style="width:100%;display:block;border-radius:14px;box-shadow:0 8px 24px rgba(31,92,53,.12);">',
        html,
    )
    if re.match(r"(?is)^\s*<section\b", html) and "max-width:677px" not in html[:400]:
        html = re.sub(
            r"(?is)^\s*<section\b([^>]*)>",
            f'<section style="{BASE_FONT_STYLE}">',
            html,
            count=1,
        )
    return html
