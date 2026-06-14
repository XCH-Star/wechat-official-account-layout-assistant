# 微信公众号内容排版助手

一个用于 Codex 的本地插件：读取微信公众号文章素材包，检查图片和占位符，优先使用增强版 HTML 模板，美化排版后创建或更新微信公众号草稿箱内容。

> 安全边界：本插件只创建或更新草稿，不发布、不群发。

## 功能

- 检查素材包是否完整。
- 自动识别 `wechat_article_template_enhanced.html`，优先使用美化模板。
- 支持普通模板 `wechat_article_template.html` 回退。
- 上传正文图片到微信公众号图文内容图片接口。
- 上传封面图为永久素材，创建草稿时生成 `thumb_media_id`。
- 创建微信公众号草稿。
- 更新已有微信公众号草稿。
- 清理空白列表项，避免公众号排版中出现空白小圆点。
- 对常见微信公众号 API 错误给出提示，例如 IP 白名单、接口权限、素材类型、`media_id` 等。

## 素材包结构

典型素材包目录：

```text
article_config.json
wechat_article_template.html
wechat_article_template_enhanced.html
article.md
layout_style_spec.md
assets/
  01_cover.png
  02_logic.png
  03_problem.png
```

`wechat_article_template_enhanced.html` 是可选文件，但建议提供。插件会默认优先使用它。

## 配置公众号密钥

复制 `.env.example` 为你自己的本地配置文件，例如 `.env.wechat.local`：

```text
WECHAT_APP_ID=your_app_id
WECHAT_APP_SECRET=your_app_secret
```

不要把真实 `.env`、AppSecret、access token 提交到仓库。

## 命令用法

检查素材包：

```powershell
python scripts/wechat_draft_package.py --env-file .env.wechat.local check --package-dir <package-dir>
```

创建草稿：

```powershell
python scripts/wechat_draft_package.py --env-file .env.wechat.local create --package-dir <package-dir>
```

更新已有草稿：

```powershell
python scripts/wechat_draft_package.py --env-file .env.wechat.local update --package-dir <package-dir> --media-id <draft-media-id>
```

更新草稿时默认沿用原封面素材。如需重新上传封面素材：

```powershell
python scripts/wechat_draft_package.py --env-file .env.wechat.local update --package-dir <package-dir> --media-id <draft-media-id> --replace-cover
```

## `article_config.json` 示例

```json
{
  "title": "文章标题",
  "author": "作者名",
  "digest": "文章摘要",
  "images": [
    {
      "name": "cover",
      "path": "assets/01_cover.png",
      "placeholder": "{{IMG_COVER_URL}}"
    },
    {
      "name": "logic",
      "path": "assets/02_logic.png",
      "placeholder": "{{IMG_LOGIC_URL}}"
    }
  ],
  "wechat_draft": {
    "show_cover_pic": 0,
    "need_open_comment": 0,
    "only_fans_can_comment": 0
  }
}
```

## Codex 使用方式

在 Codex 中，当你提供一个包含上述文件的素材包，并要求“写入微信公众号草稿箱”时，可以使用本插件的 `wechat-draft` 技能。

推荐提示词：

```text
帮我把这个公众号素材包美化排版，并写入微信公众号草稿箱。只创建草稿，不要发布。
```

## 注意事项

- 公众号需要开通并配置可用的开发者接口权限。
- 如果返回 `40164`，需要把当前服务器公网 IP 加入微信公众号后台 IP 白名单。
- 如果返回 `48001`，通常是接口权限不足。
- 图片必须通过微信公众号接口上传，不能直接使用外部图片链接。
- 本插件不会保存或打印 AppSecret、access token。

