# 📋 项目概述

**V2T (Video2Text)** 是一个视频转文字工具，支持 YouTube、Bilibili 等平台视频的自动下载、音频提取和 AI 语音转写。同时支持本地音视频文件的批量转写处理。

- **技术栈**: Python 3.9+, Gradio, yt-dlp, faster-whisper, FunASR
- **运行环境**: Windows 10/11, MacOS
- **许可证**: MIT

# 📁 项目结构

```
V2T/
├── v2t.py          # 核心转写模块 (CLI + V2T 类)
├── vlg.py          # 视频列表获取模块 (VideoListGetter)
├── vig.py          # 视频信息获取模块
├── webui.py        # Gradio Web 界面
├── requirements.txt
├── README.md
└── output/         # 默认输出目录
```
