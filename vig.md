# vig - Video Info Getter

## 简介

`vig` (Video Info Getter) 是一个命令行工具，用于爬取 Bilibili 和 YouTube 视频的元信息，包括：

- 视频标题
- 上传作者
- 上传日期
- 视频 ID
- 视频链接

该工具使用 [Crawl4AI](https://github.com/unclecode/crawl4ai) 进行网页爬取，支持批量处理多个视频链接。

## 功能特性

- ✅ **多平台支持**：支持 Bilibili 和 YouTube 两大视频平台
- ✅ **智能识别**：自动识别视频 URL 所属平台
- ✅ **批量处理**：支持同时处理多个视频链接
- ✅ **文件输入**：支持从文本文件读取 URL 列表
- ✅ **多种输出格式**：支持文本和 JSON 两种输出格式
- ✅ **Cookies 支持**：支持加载 cookies.txt 文件以访问需要登录的内容

## 支持的 URL 格式

### Bilibili

- `https://www.bilibili.com/video/BVxxxxxxxxxx`
- `https://www.bilibili.com/video/avxxxxxxxx`
- `https://b23.tv/xxxxxxx`

### YouTube

- `https://www.youtube.com/watch?v=xxxxxxxxxxx`
- `https://youtu.be/xxxxxxxxxxx`
- `https://www.youtube.com/shorts/xxxxxxxxxxx`

## 安装依赖

使用 pip 安装必要的依赖：

```bash
pip install crawl4ai
```

或者使用项目的 requirements.txt：

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法

```bash
python vig.py <视频URL>
```

### 命令行参数

| 参数 | 说明 |
|------|------|
| `urls` | 视频 URL 或包含 URL 列表的文本文件路径 |
| `-f, --format` | 输出格式，可选 `text`（默认）或 `json` |
| `-v, --verbose` | 显示详细日志信息 |

## 使用示例

### 单个视频

```bash
# Bilibili 视频
python vig.py https://www.bilibili.com/video/BV1xx411c7mD

# YouTube 视频
python vig.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### 批量处理多个视频

```bash
python vig.py url1 url2 url3
```

### 从文件读取 URL 列表

```bash
python vig.py urls.txt
```

`urls.txt` 文件格式示例：

```text
# 这是注释行，会被忽略
https://www.bilibili.com/video/BV1xx411c7mD
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/xxxxxxxxxxx
```

### 输出 JSON 格式

```bash
python vig.py https://www.bilibili.com/video/BV1xx411c7mD --format json
```

### 显示详细日志

```bash
python vig.py https://www.bilibili.com/video/BV1xx411c7mD -v
```

## 输出示例

### 文本格式输出

```
📋 共 2 个视频待处理

[Bilibili] 正在爬取: https://www.bilibili.com/video/BV1xx411c7mD
--------------------------------------------------
[YouTube] 正在爬取: https://www.youtube.com/watch?v=dQw4w9WgXcQ
--------------------------------------------------

============================================================
📹 视频信息汇总
============================================================

[1] Bilibili
    标题: 视频标题
    作者: UP主名称
    上传日期: 2024-01-01 12:00:00
    视频ID: BV1xx411c7mD
    链接: https://www.bilibili.com/video/BV1xx411c7mD

[2] YouTube
    标题: Video Title
    作者: Channel Name
    上传日期: 2024-01-01
    视频ID: dQw4w9WgXcQ
    链接: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### JSON 格式输出

```json
[
  {
    "platform": "Bilibili",
    "video_id": "BV1xx411c7mD",
    "author": "UP主名称",
    "upload_date": "2024-01-01 12:00:00",
    "title": "视频标题",
    "url": "https://www.bilibili.com/video/BV1xx411c7mD"
  },
  {
    "platform": "YouTube",
    "video_id": "dQw4w9WgXcQ",
    "author": "Channel Name",
    "upload_date": "2024-01-01",
    "title": "Video Title",
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
  }
]
```

## Cookies 支持

如果需要访问登录后才能查看的视频内容，可以提供 `cookies.txt` 文件。

### 使用方法

1. 将 `cookies.txt` 文件放置在与 `vig.py` 同一目录下
2. cookies 文件使用 Netscape/Mozilla 格式（可通过浏览器扩展导出）
3. 运行 vig.py 时会自动加载 cookies

### 获取 cookies.txt

推荐使用浏览器扩展导出 cookies：

- Chrome: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

## 注意事项

1. **网络环境**：访问 YouTube 需要能够正常访问 Google 服务
2. **反爬限制**：频繁请求可能触发平台的反爬机制，建议适当控制请求频率
3. **页面变化**：由于网页结构可能变化，信息提取可能偶尔失败

## 相关工具

- [v2t.py](./Document.md) - 视频转文字工具
- [webui.py](./README.md) - Web 用户界面
