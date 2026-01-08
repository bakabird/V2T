import gradio as gr
import os
from types import SimpleNamespace
from v2t import V2T
from vlg import VideoListGetter
from pathlib import Path
from datetime import datetime, timedelta


def generate_command(
    urls_text,
    url_file,
    engine,
    model,
    language,
    task,
    output_format,
    keep_audio,
    device,
    hotwords,
):
    """生成批量处理的 CLI 命令"""
    urls = []

    # 从文本框获取 URLs
    if urls_text:
        urls.extend([u.strip() for u in urls_text.strip().split("\n") if u.strip()])

    # 如果有上传文件，显示文件参数
    if url_file:
        cmd = f'python v2t.py "{url_file}" --engine {engine}'
    elif urls:
        if len(urls) == 1:
            cmd = f'python v2t.py "{urls[0]}" --engine {engine}'
        else:
            # 多个 URL
            urls_str = '" "'.join(urls)
            cmd = f'python v2t.py "{urls_str}" --engine {engine}'
    else:
        return ""

    if engine == "whisper":
        cmd += f" --model {model}"
    if language:
        cmd += f" --language {language}"
    cmd += f" --task {task} --format {output_format} --device {device}"
    if keep_audio:
        cmd += " --keep-audio"
    if hotwords:
        # 将多行热词合并为逗号分隔的字符串
        hw_list = [
            w.strip() for w in hotwords.replace("\n", ",").split(",") if w.strip()
        ]
        if hw_list:
            cmd += f' --hotwords "{",".join(hw_list)}"'
    return cmd


def parse_urls(urls_text, url_file):
    """解析 URLs 从文本和文件"""
    urls = []

    # 从文本框获取 URLs
    if urls_text:
        urls.extend([u.strip() for u in urls_text.strip().split("\n") if u.strip()])

    # 从上传的文件获取 URLs
    if url_file:
        try:
            with open(url_file, "r", encoding="utf-8") as f:
                file_urls = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]
                urls.extend(file_urls)
        except Exception as e:
            pass

    # 去重保持顺序
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def parse_hotwords(hotwords_text):
    """解析热词输入，支持逗号分隔和换行分隔"""
    if not hotwords_text:
        return None
    # 将换行替换为逗号，然后按逗号分隔
    hw_list = [
        w.strip() for w in hotwords_text.replace("\n", ",").split(",") if w.strip()
    ]
    if hw_list:
        return ",".join(hw_list)
    return None


# Function to run V2T in batch mode with progress updates
def run_v2t_batch(
    urls_text,
    url_file,
    engine,
    model,
    language,
    task,
    output_format,
    keep_audio,
    device,
    hotwords,
):
    """批量处理视频转文字，使用 generator 实时更新进度"""

    urls = parse_urls(urls_text, url_file)

    if not urls:
        yield "❌ 请输入至少一个视频 URL", [], []
        return

    total = len(urls)
    results = []  # [(url, status, message)]
    all_files = []

    # 解析热词
    parsed_hotwords = parse_hotwords(hotwords)
    if parsed_hotwords:
        yield f"🚀 开始批量处理 {total} 个视频...\n📝 热词: {parsed_hotwords}\n", [], []
    else:
        yield f"🚀 开始批量处理 {total} 个视频...\n", [], []

    for idx, url in enumerate(urls, 1):
        # 更新进度
        progress_msg = f"📊 进度: {idx}/{total}\n"
        progress_msg += f"▶️ 正在处理: {url[:60]}...\n\n"

        # 显示已完成的任务状态
        for r_url, r_status, r_msg in results:
            status_icon = "✅" if r_status == "success" else "❌"
            progress_msg += f"{status_icon} {r_url[:50]}... - {r_msg}\n"

        yield progress_msg, all_files, [
            [r[0][:50], "✅ 成功" if r[1] == "success" else "❌ 失败", r[2]]
            for r in results
        ]

        try:
            # Create args for single URL
            args = SimpleNamespace(
                urls=[url],
                engine=engine,
                model=model,
                language=language if language else None,
                task=task,
                output="./output",
                device=device,
                keep_audio=keep_audio,
                format=output_format,
                cookies=None,
                hotwords=parsed_hotwords,
            )

            app = V2T(args)
            app.run()

            # Find new files created
            output_dir = Path("./output")
            if output_dir.exists():
                # Get files modified in last minute
                import time

                current_time = time.time()
                for f in output_dir.iterdir():
                    if f.is_file() and (current_time - f.stat().st_mtime) < 120:
                        if str(f) not in all_files:
                            all_files.append(str(f))

            results.append((url, "success", "处理完成"))

        except Exception as e:
            results.append((url, "error", str(e)[:50]))

    # 最终状态
    success_count = sum(1 for r in results if r[1] == "success")
    fail_count = total - success_count

    final_msg = f"🏁 批量处理完成!\n\n"
    final_msg += f"📊 统计: 成功 {success_count}/{total}, 失败 {fail_count}/{total}\n\n"
    final_msg += "详细结果:\n"
    for r_url, r_status, r_msg in results:
        status_icon = "✅" if r_status == "success" else "❌"
        final_msg += f"{status_icon} {r_url[:60]}... - {r_msg}\n"

    result_table = [
        [r[0][:60], "✅ 成功" if r[1] == "success" else "❌ 失败", r[2]]
        for r in results
    ]

    yield final_msg, all_files, result_table


# ==================== Video List Getter Functions ====================


def generate_vlg_command(
    channel_url, date_mode, days, start_date, end_date, max_videos
):
    """生成 VLG 命令行"""
    if not channel_url:
        return ""

    cmd = f'python vlg.py "{channel_url}"'

    if date_mode == "最近N天" and days:
        cmd += f" --days {days}"
    elif date_mode == "指定日期范围":
        if start_date:
            cmd += f" --start {start_date}"
        if end_date:
            cmd += f" --end {end_date}"

    if max_videos:
        cmd += f" --max {max_videos}"

    return cmd


def run_vlg(channel_url, date_mode, days, start_date, end_date, max_videos):
    """运行视频列表获取"""
    if not channel_url:
        return "请输入频道/作者 URL", None, [], ""

    try:
        getter = VideoListGetter()

        # 根据日期模式设置参数
        start = None
        end = None
        days_param = None

        if date_mode == "最近N天" and days:
            days_param = int(days)
        elif date_mode == "指定日期范围":
            start = start_date if start_date else None
            end = end_date if end_date else None

        max_v = int(max_videos) if max_videos else None

        # 运行获取
        videos, csv_path = getter.run(
            channel_url=channel_url,
            start_date=start,
            end_date=end,
            days=days_param,
            max_videos=max_v,
        )

        if not videos:
            return "未找到符合条件的视频", None, [], ""

        # 构建预览数据
        preview_data = []
        urls_for_v2t = []
        for v in videos[:50]:  # 最多显示50条
            preview_data.append(
                [
                    v.upload_date,
                    v.title[:50] + "..." if len(v.title) > 50 else v.title,
                    v.author,
                    v.url,
                ]
            )
            urls_for_v2t.append(v.url)

        status = f"✅ 成功获取 {len(videos)} 个视频"
        if len(videos) > 50:
            status += f" (预览前50条)"

        # 生成可传递到 V2T 的 URL 列表
        urls_text = "\n".join(urls_for_v2t)

        return status, csv_path, preview_data, urls_text

    except Exception as e:
        return f"❌ 错误: {str(e)}", None, [], ""


# Define Gradio Interface
with gr.Blocks(title="Video2Text WebUI", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎬 Video2Text WebUI")
    gr.Markdown(
        "视频转文字工具 - 支持 Whisper 和 FunASR (SenseVoice) 引擎，支持批量处理"
    )

    # 用于在 Tab 之间传递数据的状态
    vlg_urls_state = gr.State("")

    with gr.Tabs():
        # ==================== Tab 1: Video to Text (Batch) ====================
        with gr.TabItem("🎬 视频转文字"):
            gr.Markdown("### 支持批量处理多个视频")

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("#### 输入视频 URL")

                    with gr.Tab("📝 手动输入"):
                        urls_input = gr.Textbox(
                            label="视频 URLs (每行一个)",
                            placeholder="https://www.youtube.com/watch?v=xxx\nhttps://www.bilibili.com/video/BVxxx\n...",
                            lines=6,
                            max_lines=20,
                        )

                    with gr.Tab("📁 文件上传"):
                        url_file_input = gr.File(
                            label="上传包含 URL 的文本文件",
                            file_types=[".txt"],
                            type="filepath",
                        )
                        gr.Markdown("*文件格式: 每行一个 URL，以 # 开头的行会被忽略*")

                    # 接收来自 VLG 的 URLs
                    with gr.Accordion("📋 从视频列表导入", open=False):
                        vlg_urls_display = gr.Textbox(
                            label="来自视频列表获取的 URLs",
                            placeholder="在「视频列表获取」Tab 中获取视频后，点击「发送到视频转文字」按钮",
                            lines=4,
                            interactive=False,
                        )
                        use_vlg_urls_btn = gr.Button("📥 使用这些 URLs", size="sm")

                    with gr.Accordion("⚙️ 转写配置", open=True):
                        engine_input = gr.Dropdown(
                            choices=["whisper", "funasr"],
                            value="whisper",
                            label="ASR 引擎",
                            info="Whisper: 通用多语言 (OpenAI). FunASR: 中文优化 (阿里)",
                        )

                        model_input = gr.Dropdown(
                            choices=["tiny", "base", "small", "medium", "large-v3"],
                            value="small",
                            label="Whisper 模型大小",
                            info="使用 FunASR 时此选项无效",
                        )

                        language_input = gr.Textbox(
                            label="语言 (可选)",
                            placeholder="例如: 'zh', 'en'. 留空自动检测",
                        )

                        task_input = gr.Dropdown(
                            choices=["transcribe", "translate"],
                            value="transcribe",
                            label="任务类型",
                            info="translate 会翻译成英文",
                        )

                        format_input = gr.Dropdown(
                            choices=["txt", "srt", "all"],
                            value="txt",
                            label="输出格式",
                        )

                        device_input = gr.Dropdown(
                            choices=["cpu", "cuda"],
                            value="cpu",
                            label="计算设备",
                            info="cuda 需要 NVIDIA GPU",
                        )

                        keep_audio_input = gr.Checkbox(
                            label="保留下载的音频文件", value=False
                        )

                        hotwords_input = gr.Textbox(
                            label="热词 (Hotwords)",
                            placeholder="输入热词提高识别准确率\n每行一个或用逗号分隔\n例如: GPT, LLM, Transformer\n或中文: 人工智能, 机器学习",
                            lines=3,
                            info="用于提升特定词汇的识别率，支持中英文",
                        )

                    command_output = gr.Textbox(
                        label="CLI 命令预览",
                        interactive=False,
                        lines=3,
                    )

                    submit_btn = gr.Button(
                        "🚀 开始批量处理", variant="primary", size="lg"
                    )

                with gr.Column(scale=1):
                    output_log = gr.Textbox(
                        label="处理日志",
                        lines=12,
                        max_lines=20,
                    )

                    output_files = gr.File(
                        label="生成的文件",
                        file_count="multiple",
                    )

                    result_table = gr.Dataframe(
                        headers=["URL", "状态", "信息"],
                        label="处理结果汇总",
                        wrap=True,
                    )

            # 将 VLG URLs 复制到输入框
            def copy_vlg_urls(vlg_urls):
                return vlg_urls

            use_vlg_urls_btn.click(
                fn=copy_vlg_urls,
                inputs=[vlg_urls_display],
                outputs=[urls_input],
            )

            # Inputs list for binding
            v2t_inputs = [
                urls_input,
                url_file_input,
                engine_input,
                model_input,
                language_input,
                task_input,
                format_input,
                keep_audio_input,
                device_input,
                hotwords_input,
            ]

            # Bind events for live CLI command update
            for input_component in [
                urls_input,
                url_file_input,
                engine_input,
                model_input,
                language_input,
                task_input,
                format_input,
                keep_audio_input,
                device_input,
                hotwords_input,
            ]:
                input_component.change(
                    fn=generate_command,
                    inputs=v2t_inputs,
                    outputs=command_output,
                )

            submit_btn.click(
                fn=run_v2t_batch,
                inputs=v2t_inputs,
                outputs=[output_log, output_files, result_table],
            )

        # ==================== Tab 2: Video List Getter ====================
        with gr.TabItem("📋 视频列表获取"):
            gr.Markdown("### 获取频道/作者的视频列表")
            gr.Markdown(
                "支持 YouTube 和 Bilibili 平台，可按时间范围筛选并导出为 CSV 文件。"
            )

            with gr.Row():
                with gr.Column():
                    vlg_url_input = gr.Textbox(
                        label="频道/作者 URL",
                        placeholder="例如: https://www.youtube.com/@channel 或 https://space.bilibili.com/12345678",
                        info="输入 YouTube 频道或 Bilibili 用户主页链接",
                    )

                    with gr.Accordion("时间范围设置", open=True):
                        date_mode = gr.Radio(
                            choices=["不限制", "最近N天", "指定日期范围"],
                            value="不限制",
                            label="时间筛选模式",
                        )

                        with gr.Row():
                            days_input = gr.Number(
                                label="最近天数", value=30, precision=0, visible=False
                            )

                        with gr.Row():
                            start_date_input = gr.Textbox(
                                label="开始日期",
                                placeholder="YYYY-MM-DD",
                                visible=False,
                            )
                            end_date_input = gr.Textbox(
                                label="结束日期",
                                placeholder="YYYY-MM-DD",
                                visible=False,
                            )

                    max_videos_input = gr.Number(
                        label="最大视频数量 (留空表示不限制)", precision=0
                    )

                    vlg_command_output = gr.Textbox(
                        label="CLI 命令", interactive=False, lines=2
                    )

                    vlg_submit_btn = gr.Button("🚀 获取视频列表", variant="primary")

                with gr.Column():
                    vlg_status = gr.Textbox(label="状态")
                    vlg_file = gr.File(label="下载 CSV 文件")
                    vlg_preview = gr.Dataframe(
                        headers=["发布时间", "标题", "作者", "URL"],
                        label="预览 (最多显示50条)",
                        wrap=True,
                    )

                    # 发送到 V2T 按钮
                    send_to_v2t_btn = gr.Button(
                        "📤 发送到视频转文字", variant="secondary"
                    )
                    vlg_urls_hidden = gr.Textbox(visible=False)  # 隐藏的 URL 存储

            # 日期模式切换逻辑
            def update_date_visibility(mode):
                if mode == "最近N天":
                    return (
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=False),
                    )
                elif mode == "指定日期范围":
                    return (
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=True),
                    )
                else:
                    return (
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                    )

            date_mode.change(
                fn=update_date_visibility,
                inputs=[date_mode],
                outputs=[days_input, start_date_input, end_date_input],
            )

            # VLG 输入列表
            vlg_inputs = [
                vlg_url_input,
                date_mode,
                days_input,
                start_date_input,
                end_date_input,
                max_videos_input,
            ]

            # 实时更新命令
            for input_component in vlg_inputs:
                input_component.change(
                    fn=generate_vlg_command,
                    inputs=vlg_inputs,
                    outputs=vlg_command_output,
                )

            vlg_submit_btn.click(
                fn=run_vlg,
                inputs=vlg_inputs,
                outputs=[vlg_status, vlg_file, vlg_preview, vlg_urls_hidden],
            )

            # 发送 URLs 到 V2T Tab
            send_to_v2t_btn.click(
                fn=lambda urls: urls,
                inputs=[vlg_urls_hidden],
                outputs=[vlg_urls_display],
            )

if __name__ == "__main__":
    demo.launch(share=False)
