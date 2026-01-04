产品需求文档 (PRD) - 视频转文字命令行工具 (Video2Text CLI)

版本号: v2.1 (macOS 专属版)
状态: 待开发
最后更新: 2026-01-03

1. 项目背景与目标

1.1 目标

开发一款轻量级 命令行工具 (CLI)，无需图形界面，通过终端指令即可完成“视频下载 -> 音频提取 -> AI转写 -> 生成文稿”的全自动化流程。

1.2 适用平台

macOS (Terminal)

推荐硬件: Apple Silicon (M1/M2/M3 等) 机型。由于 faster-whisper 在 ARM64 架构上有极好的优化，使用 CPU 运行量化模型即可获得极快的速度，无需强制 GPU 加速。

2. 核心业务流程

用户在 Terminal 执行命令 -> 工具自动拉取视频流 -> 提取音频到临时目录 -> 调用本地 Whisper 模型 -> 输出文本文件 -> 清理临时文件。

3. 功能需求详情 (Functional Requirements)

3.1 命令行参数 (Arguments)

工具应支持以下参数：

urls: (必选) 一个或多个视频链接，或包含链接的 .txt 文件路径。

--model: (可选) 指定 Whisper 模型大小 (tiny, base, small, medium, large-v3)。默认为 small。

--language: (可选) 强制指定源语言代码（如 'zh', 'en', 'ja'），避免自动检测错误。

--task: (可选) 任务类型 ('transcribe' 或 'translate')。默认为 'transcribe'。

--output, -o: (可选) 结果输出目录。默认为 ./output。

--device: (可选) 指定运行设备。在 macOS 上默认为 cpu (推荐)。

--keep-audio: (可选) 是否保留下载的音频文件。默认转写完成后删除。

--format: (可选) 输出格式 (txt, srt, all)。默认为 txt。

3.2 媒体下载 (Downloader)

引擎: yt-dlp (Python Library)。

策略: 仅下载最佳音频流，自动转换为适配 Whisper 的格式。支持加载本地 Cookies 文件（如 'cookies.txt'）以访问受限内容。

文件名: 格式为 '

$$标题$$

_

$$视频ID$$

'，并清洗非法字符以防止文件名冲突。

3.3 语音转文字 (Transcriber)

引擎: faster-whisper (基于 CTranslate2，针对 macOS ARM64 优化)。

进度展示: 在终端显示加载模型进度条、转写时间段进度。

3.4 异常处理与环境检查

FFmpeg 检查: 程序启动时检查是否安装 ffmpeg。若未安装，提示用户运行 brew install ffmpeg。

下载失败: 若下载失败（如网络原因），跳过当前视频并记录错误，继续处理下一个。

4. 技术栈

语言: Python 3.9+ (建议使用 brew install python 获取最新版)

核心库:

argparse: 命令行参数解析

yt-dlp: 媒体下载

faster-whisper: 语音识别 (底层依赖 CTranslate2)

tqdm: 终端进度条

5. 使用示例 (Usage Examples)

场景 A：转换单个视频

python3 v2t.py "[https://www.youtube.com/watch?v=xxxx](https://www.youtube.com/watch?v=xxxx)"


场景 B：使用大模型转换列表 (Apple Silicon)

由于 M 系列芯片 CPU 性能强大，直接运行 large-v3 模型依然流畅。

python3 v2t.py urls.txt --model large-v3 --format all
