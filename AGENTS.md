# AGENTS.md - V2T 项目速查表

> 本文档供 AI Agent 快速了解项目结构和关键信息。

## 📋 项目概述

**V2T (Video2Text)** 是一个视频转文字工具，支持 YouTube、Bilibili 等平台视频的自动下载、音频提取和 AI 语音转写。

- **技术栈**: Python 3.9+, Gradio, yt-dlp, faster-whisper, FunASR
- **运行环境**: Windows 10/11, 需要 FFmpeg
- **许可证**: MIT

## 📁 项目结构

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

## 🔧 核心模块

### v2t.py
- **V2T 类**: 主要业务逻辑，支持批量 URL 处理
- **WhisperEngine**: faster-whisper 引擎封装
- **FunASREngine**: 阿里 SenseVoice 引擎封装
- **Segment**: 转写结果数据类 (start, end, text)

### vlg.py
- **VideoListGetter**: 获取频道/用户的视频列表
- 支持 YouTube 和 Bilibili
- 支持时间范围筛选

### webui.py
- **Gradio Blocks** 构建的 Web 界面
- Tab 1: 视频转文字 (支持批量处理)
- Tab 2: 视频列表获取

## 🎯 关键函数

### webui.py

| 函数 | 用途 |
|------|------|
| `run_v2t_batch()` | 批量处理视频转文字 (generator，实时进度) |
| `parse_urls()` | 解析 URLs (文本框 + 文件上传) |
| `generate_command()` | 生成 CLI 命令预览 |
| `run_vlg()` | 运行视频列表获取 |
| `generate_vlg_command()` | 生成 VLG CLI 命令 |

### v2t.py

| 函数/类 | 用途 |
|---------|------|
| `V2T.run()` | 主入口，遍历 URL 列表进行处理 |
| `V2T.download_audio()` | 使用 yt-dlp 下载音频 |
| `V2T.write_txt/srt()` | 输出文件写入 |
| `TranscriberEngine` | ASR 引擎基类 |

## 🔄 数据流

```
用户输入 URLs
     ↓
webui.py: parse_urls() → run_v2t_batch()
     ↓
v2t.py: V2T.download_audio() → Transcriber.transcribe()
     ↓
输出: ./output/{date}_{author}_{title}_{id}.txt/srt
```

## ⚠️ 注意事项

1. **模型首次加载**: 会自动下载模型权重到缓存目录
2. **FFmpeg 依赖**: 必须安装并加入 PATH
3. **Cookies**: 支持 cookies.txt 下载限制视频
4. **批量处理**: WebUI 使用 generator 实现实时进度更新

## 📝 变更记录

### 2025-01-XX: WebUI 批量处理功能

**变更文件**: `webui.py`

**新增功能**:
- 批量 URL 输入 (多行文本框 + 文件上传)
- `run_v2t_batch()`: 使用 generator 实现实时进度更新
- `parse_urls()`: 合并解析文本框和上传文件的 URLs
- VLG → V2T 集成: 「发送到视频转文字」按钮
- 处理结果表格: 显示每个视频的状态和信息

**UI 变更**:
- 视频转文字 Tab 重构，增加子 Tab (手动输入/文件上传)
- 新增「从视频列表导入」Accordion
- 新增处理结果 Dataframe 汇总表
- VLG Tab 增加「发送到视频转文字」按钮

**修改函数**:
- `generate_command()`: 支持批量 URL 命令生成
- `run_vlg()`: 返回值增加 urls_text 用于 Tab 间传递

### 2025-01-08: 热词 (Hotwords) 支持

**变更文件**: `v2t.py`, `webui.py`

**新增功能**:
- 支持热词设置，提高特定词汇的语音识别准确率
- 同时支持 Whisper (faster-whisper) 和 FunASR (SenseVoice) 两种引擎
- 热词可通过 CLI 参数 `--hotwords` 或 WebUI 输入框配置

**v2t.py 变更**:
- `TranscriberEngine.transcribe()`: 基类方法签名新增 `hotwords: Optional[str]` 参数
- `WhisperEngine.transcribe()`: 将 hotwords 传递给 faster-whisper 的 `transcribe()` 调用
- `FunASREngine.transcribe()`: 将 hotwords 以 `hotword` 参数名传递给 FunASR 的 `generate()` 调用
- `V2T.run()`: 从 args 获取热词并传递给转写引擎
- CLI argparse: 新增 `--hotwords` 选项

**webui.py 变更**:
- 新增 `parse_hotwords()`: 解析热词输入，支持逗号分隔和换行分隔
- `generate_command()`: 新增 hotwords 参数，生成带热词的 CLI 命令
- `run_v2t_batch()`: 新增 hotwords 参数，传递给 V2T 处理流程
- UI: 在「转写配置」区域新增热词输入框 (`hotwords_input`)

**使用方式**:
- CLI: `python v2t.py <url> --hotwords "GPT,LLM,Transformer"`
- WebUI: 在热词输入框中输入词汇，每行一个或用逗号分隔

### 2025-01-08: FunASR 多模型支持

**变更文件**: `v2t.py`, `webui.py`

**新增功能**:
- FunASR 引擎新增 Paraformer-large 和 Paraformer-large-zh-16k 模型支持
- 支持通过 CLI 参数或 WebUI 选择 FunASR 模型
- 根据模型类型自动选择不同的输出解析逻辑

**支持的 FunASR 模型**:
| 模型名称 | ModelScope 路径 | 特点 |
|---------|----------------|------|
| `sensevoicesmall` | `iic/SenseVoiceSmall` | 多语言支持，带情感识别，默认选项 |
| `paraformer-large` | `iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | 高精度中文 ASR |
| `paraformer-large-zh-16k` | `iic/speech_paraformer-large-long_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | 长音频中文 ASR |

**v2t.py 变更**:
- 新增 `FUNASR_MODELS` 字典: FunASR 模型名称到 ModelScope 路径的映射
- `FunASREngine.__init__()`: 新增 `model_name` 参数，支持动态选择模型
- 新增 `FunASREngine._parse_paraformer_output()`: Paraformer 模型输出解析方法
- `FunASREngine.transcribe()`: 根据模型类型选择解析逻辑和生成参数
- CLI argparse: 新增 `--funasr-model` 选项，可选值: `sensevoicesmall`, `paraformer-large`, `paraformer-large-zh-16k`
- `V2T.__init__()`: 将 `funasr_model` 参数传递给 FunASREngine

**webui.py 变更**:
- 新增 `funasr_model_input` 下拉框: FunASR 模型选择 UI 组件
- `update_model_visibility()`: 引擎切换时显示/隐藏对应模型选择框
- `generate_command()`: 新增 `funasr_model` 参数，生成带模型选择的 CLI 命令
- `run_v2t_batch()`: 新增 `funasr_model` 参数，传递给 V2T 处理流程

**使用方式**:
- CLI: `python v2t.py <url> --engine funasr --funasr-model paraformer-large`
- WebUI: 选择 FunASR 引擎后，在「FunASR 模型」下拉框中选择模型
