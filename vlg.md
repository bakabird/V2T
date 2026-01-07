# VLG - Video List Getter

视频列表获取工具，使用 yt-dlp 获取作者/频道的视频列表，并导出为 CSV 文件。

## 功能特点

- 📺 **多平台支持**：支持 YouTube 和 Bilibili 平台
- 📅 **时间范围过滤**：可按日期范围或最近 N 天筛选视频
- 📊 **CSV 导出**：输出标准 CSV 格式，支持 Excel 打开
- 🖥️ **双模式使用**：支持命令行 (CLI) 和图形界面 (WebUI)

## 输出格式

CSV 文件包含以下列：

| 发布时间 | 标题 | 作者 | 视频链接 |
|---------|------|------|---------|
| 2024-01-15 | 视频标题 | 作者名称 | https://... |

## 安装依赖

```bash
pip install yt-dlp
```

或使用项目的 requirements.txt：

```bash
pip install -r requirements.txt
```

## 命令行使用

### 基本用法

```bash
# 获取 YouTube 频道的所有视频
python vlg.py https://www.youtube.com/@channel_name

# 获取 Bilibili 用户的所有视频
python vlg.py https://space.bilibili.com/12345678
```

### 时间范围筛选

```bash
# 获取最近 30 天的视频
python vlg.py https://www.youtube.com/@channel_name --days 30

# 获取指定日期范围的视频
python vlg.py https://www.youtube.com/@channel_name --start 2024-01-01 --end 2024-06-30

# 只指定开始日期（从该日期到现在）
python vlg.py https://www.youtube.com/@channel_name --start 2024-01-01

# 只指定结束日期（从最早到该日期）
python vlg.py https://www.youtube.com/@channel_name --end 2024-06-30
```

### 限制数量

```bash
# 最多获取 100 个视频
python vlg.py https://www.youtube.com/@channel_name --max 100
```

### 指定输出文件

```bash
# 指定输出文件路径
python vlg.py https://www.youtube.com/@channel_name -o my_videos.csv

# 输出到指定目录
python vlg.py https://www.youtube.com/@channel_name -o ./data/channel_videos.csv
```

### 使用 Cookies

如果需要访问需要登录的内容，可以使用 cookies 文件：

```bash
python vlg.py https://www.youtube.com/@channel_name --cookies cookies.txt
```

> cookies.txt 需要是 Netscape/Mozilla 格式，可以使用浏览器扩展（如 Get cookies.txt）导出。

### 完整参数列表

```
usage: vlg.py [-h] [-o OUTPUT] [--start START] [--end END] [--days DAYS]
              [--max MAX] [--cookies COOKIES] [-v]
              url

参数说明：
  url                 频道/作者 URL (支持 YouTube 和 Bilibili)
  -o, --output        输出 CSV 文件路径 (默认: ./output/video_list_时间戳.csv)
  --start             开始日期 (YYYY-MM-DD 格式)
  --end               结束日期 (YYYY-MM-DD 格式)
  --days              获取最近 N 天的视频 (与 --start/--end 互斥)
  --max               最大视频数量
  --cookies           Cookies 文件路径 (Netscape 格式)
  -v, --verbose       显示详细日志
```

## WebUI 使用

### 启动 WebUI

```bash
python webui.py
```

浏览器访问 `http://127.0.0.1:7860` 后，切换到 "📋 视频列表获取" 标签页。

### WebUI 功能

1. **输入频道 URL**：在文本框中输入 YouTube 频道或 Bilibili 用户主页链接

2. **时间筛选模式**：
   - **不限制**：获取所有视频
   - **最近N天**：输入天数，如 30 表示最近 30 天
   - **指定日期范围**：输入开始和结束日期

3. **最大视频数量**：可选，限制获取的视频数量

4. **获取视频列表**：点击按钮开始获取

5. **查看结果**：
   - 预览表格显示前 20 条视频
   - 点击下载 CSV 文件

## 支持的 URL 格式

### YouTube

- 频道主页：`https://www.youtube.com/@channel_name`
- 频道 ID：`https://www.youtube.com/channel/UCxxxxxxxx`
- 旧式用户页：`https://www.youtube.com/user/username`
- 自定义 URL：`https://www.youtube.com/c/customname`

### Bilibili

- 用户空间：`https://space.bilibili.com/12345678`
- 带路径：`https://space.bilibili.com/12345678/video`

## 示例输出

```
============================================================
📹 Video List Getter
============================================================
📺 平台: YOUTUBE
🔗 URL: https://www.youtube.com/@example/videos
⏳ 正在获取视频列表...
📅 时间范围: 从 2024-01-01 到 2024-06-30
📊 找到 150 个视频
✅ 筛选后共 42 个视频
💾 已导出到: C:\Users\...\output\video_list_20240615_143022.csv

============================================================
✅ 完成! 共导出 42 个视频
============================================================
```

## 注意事项

1. **网络要求**：需要能够访问 YouTube 或 Bilibili 的网络环境

2. **速率限制**：频繁请求可能触发平台的速率限制，建议适当控制请求频率

3. **日期准确性**：部分视频可能没有精确的上传日期信息，这些视频会显示"未知"

4. **大型频道**：对于视频数量很多的频道，获取过程可能需要较长时间

## 常见问题

### Q: 为什么有些视频的日期显示"未知"？

A: yt-dlp 使用 `extract_flat` 模式快速获取列表，某些视频可能没有返回上传日期。这通常发生在直播、首播或特殊类型的视频上。

### Q: 如何获取私有/会员视频？

A: 需要使用 `--cookies` 参数提供登录后的 cookies 文件。

### Q: 获取 Bilibili 视频列表很慢？

A: Bilibili 的分页机制可能需要多次请求，视频数量多时会比较慢。可以使用 `--max` 参数限制数量。

## 相关文件

- `vlg.py` - 视频列表获取器主程序
- `webui.py` - 包含 VLG 功能的 Web 界面
- `cookies.txt` - 可选的 cookies 文件（需自行创建）
