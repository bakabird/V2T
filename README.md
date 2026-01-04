# Video2Text CLI (V2T)

一个轻量级的命令行工具，用于将视频自动转换为文字稿。支持 YouTube、Bilibili 等主流视频平台，利用 OpenAI Whisper 模型在本地进行高质量语音转写。

## 🌟 特性

*   **全自动化**：下载 -> 音频提取 -> AI 转写 -> 导出文稿，一键完成。
*   **本地隐私**：使用 `faster-whisper` 在本地运行模型，数据不上传云端。
*   **双引擎支持**：
    *   **Whisper** (默认)：通用性强，OpenAI 出品。
    *   **FunASR (SenseVoice)**：针对中文优化，识别准确率极高，速度快。
*   **WebUI 界面**：提供可视化的 Web 界面，操作更便捷。
*   **多格式支持**：支持导出 `.txt` 纯文本和 `.srt` 字幕文件。
*   **Cookie 支持**：支持加载 cookies.txt 以下载会员/年龄限制视频。

## 🛠️ 安装

### 1. 前置要求

*   Windows 10/11
*   Python 3.9+
*   FFmpeg (必须安装)

推荐使用 `winget` 安装 FFmpeg:

```powershell
winget install ffmpeg
```

或者从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到系统环境变量 PATH 中。

### 2. 获取代码与安装依赖

```bash
# 克隆仓库 (如果您有 git) 或下载源码
git clone https://github.com/your-username/V2T.git
cd V2T

# 安装 Python 依赖
pip install -r requirements.txt
```

## 🚀 使用指南

### ⚡️ 性能优化指南

为了获得最佳的转写速度，建议根据您的硬件选择合适的配置：

#### 1. Windows 用户 (NVIDIA GPU)
*   **推荐配置**：`--device cuda`
*   **前提条件**：
    *   安装 NVIDIA 显卡驱动。
    *   安装 CUDA Toolkit (推荐 11.8 或 12.x)。
    *   安装支持 CUDA 的 PyTorch 版本（仅 FunASR 需要）。
    *   对于 `faster-whisper`，需要确保安装了 cuDNN 库（通常包含在 CUDA Toolkit 中或单独安装）。
*   **如何启用**：
    *   **命令行**：添加参数 `--device cuda`
    *   **WebUI**：在 "Device" 选项中选择 "cuda"。

#### 3. 模型选择建议 (Whisper)
*   **tiny / base**: 极快，适合对精度要求不高的场景。
*   **small**: 速度与精度的平衡点，**推荐日常使用**。
*   **medium**: 精度更高，但在 CPU 上速度较慢。
*   **large-v3**: 最高精度，建议仅在有高性能 GPU 或对时间不敏感时使用。

---

### 🖥️ WebUI 界面 (推荐)

如果您更喜欢图形界面，可以直接启动 WebUI：

```bash
python webui.py
```

启动后，在浏览器中访问显示的本地链接（通常是 `http://127.0.0.1:7860`）。

### 💻 命令行用法

### 基本用法

直接转换单个视频：

```bash
python v2t.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### 批量处理

创建一个包含多个链接的文本文件 `urls.txt`：

```text
https://www.youtube.com/watch?v=video1
https://www.bilibili.com/video/BVxxx
```

然后运行：

```bash
python v2t.py urls.txt
```

### 常用参数

| 参数 | 说明 | 示例 |
| :--- | :--- | :--- |
| `urls` | 视频链接或链接文件路径 | `python v2t.py url1 url2` |
| `--engine` | ASR 引擎: `whisper` (默认) 或 `funasr` (SenseVoice) | `--engine funasr` |
| `--model` | Whisper 模型大小 (tiny/base/small/medium/large-v3) | `--model large-v3` (默认 small) |
| `--language` | 强制指定源语言代码 | `--language zh` (默认自动检测) |
| `--task` | 任务类型: `transcribe`(转写) 或 `translate`(翻译为英文) | `--task translate` |
| `--output`, `-o` | 输出目录 | `-o ./my_docs` |
| `--format` | 输出格式: `txt`, `srt`, `all` | `--format srt` |
| `--cookies` | 指定 cookies.txt 文件路径 | `--cookies ./cookies.txt` |
| `--keep-audio` | 保留下载的音频文件 (默认删除) | `--keep-audio` |

### 高级示例

**使用 Large-v3 模型并导出 SRT 字幕：**

```bash
python v2t.py "https://youtu.be/xxx" --model large-v3 --format srt
```

**使用 Cookie 下载会员视频：**

将导出的 `cookies.txt` 放在同级目录，或手动指定：

```bash
python v2t.py "https://www.bilibili.com/video/BVxxx" --cookies ./my_cookies.txt
```

## 📝 注意事项

*   **模型下载**：首次运行某个模型（如 `small`）时，程序会自动从 Hugging Face 下载模型权重，请保持网络通畅。
*   **文件名**：输出文件名格式为 `标题_视频ID`，会自动去除非法字符。

## 📄 许可证

MIT License
