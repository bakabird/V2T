import gradio as gr
import os
from types import SimpleNamespace
from v2t import V2T
from vlg import VideoListGetter
from pathlib import Path
from datetime import datetime, timedelta


def generate_command(
    url, engine, model, language, task, output_format, keep_audio, device
):
    if not url:
        return ""

    cmd = f'python v2t.py "{url}" --engine {engine}'
    if engine == "whisper":
        cmd += f" --model {model}"
    if language:
        cmd += f" --language {language}"
    cmd += f" --task {task} --format {output_format} --device {device}"
    if keep_audio:
        cmd += " --keep-audio"
    return cmd


# Function to run V2T
def run_v2t(url, engine, model, language, task, output_format, keep_audio, device):
    if not url:
        return "Please enter a video URL.", []

    # Create args
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
    )

    try:
        app = V2T(args)
        app.run()

        # Find generated files
        output_dir = Path("./output")
        if not output_dir.exists():
            return "Output directory not found.", []

        # Sort by modification time
        files = sorted(output_dir.iterdir(), key=os.path.getmtime, reverse=True)

        # Filter recently modified files (last 2 minutes?) or just top 5
        recent_files = [str(f) for f in files[:5]]

        return (
            f"Successfully processed: {url}\nCheck the files below.",
            recent_files,
        )

    except Exception as e:
        return f"Error: {str(e)}", []


# ==================== Video List Getter Functions ====================


def generate_vlg_command(
    channel_url, date_mode, days, start_date, end_date, max_videos
):
    """生成 VLG 命令行"""
    if not channel_url:
        return ""

    cmd = f'python vlg.py "{channel_url}"'

    if date_mode == "最近N天" and days:
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
        return "请输入频道/作者 URL", None, []

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
            return "未找到符合条件的视频", None, []

        # 构建预览数据
        preview_data = []
        for v in videos[:20]:  # 只预览前20条
            preview_data.append(
                [
                    v.upload_date,
                    v.title[:50] + "..." if len(v.title) > 50 else v.title,
                    v.author,
                ]
            )

        status = f"✅ 成功获取 {len(videos)} 个视频"
        if len(videos) > 20:
            status += f" (预览前20条)"

        return status, csv_path, preview_data

    except Exception as e:
        return f"❌ 错误: {str(e)}", None, []


# Define Gradio Interface
with gr.Blocks(title="Video2Text WebUI") as demo:
    gr.Markdown("# Video2Text WebUI")
    gr.Markdown("Convert Video to Text using Whisper or FunASR (SenseVoice).")

    with gr.Tabs():
        # ==================== Tab 1: Video to Text ====================
        with gr.TabItem("🎬 视频转文字"):
            with gr.Row():
                with gr.Column():
                    url_input = gr.Textbox(
                        label="Video URL",
                        placeholder="https://www.youtube.com/watch?v=...",
                    )

                    with gr.Accordion("Configuration", open=True):
                        engine_input = gr.Dropdown(
                            choices=["whisper", "funasr"],
                            value="whisper",
                            label="ASR Engine",
                            info="Whisper: General purpose (OpenAI). FunASR: Optimized for Chinese (Alibaba).",
                        )

                        model_input = gr.Dropdown(
                            choices=["tiny", "base", "small", "medium", "large-v3"],
                            value="small",
                            label="Whisper Model Size",
                            info="Ignored if using FunASR.",
                        )

                        language_input = gr.Textbox(
                            label="Language (Optional)",
                            placeholder="e.g., 'zh', 'en'. Leave empty for auto-detection.",
                        )

                        task_input = gr.Dropdown(
                            choices=["transcribe", "translate"],
                            value="transcribe",
                            label="Task",
                            info="Translate will translate to English.",
                        )

                        format_input = gr.Dropdown(
                            choices=["txt", "srt", "all"],
                            value="txt",
                            label="Output Format",
                        )

                        device_input = gr.Dropdown(
                            choices=["cpu", "cuda"],
                            value="cpu",
                            label="Device",
                            info="Use 'cuda' for NVIDIA GPU (requires configured environment), 'cpu' for others.",
                        )

                        keep_audio_input = gr.Checkbox(
                            label="Keep Audio File", value=False
                        )

                    command_output = gr.Textbox(
                        label="CLI Command",
                        interactive=False,
                        lines=4,
                    )

                    submit_btn = gr.Button("Start Processing", variant="primary")

                with gr.Column():
                    output_log = gr.Textbox(label="Status Log")
                    output_files = gr.File(label="Generated Files")

            # Inputs list for binding
            inputs = [
                url_input,
                engine_input,
                model_input,
                language_input,
                task_input,
                format_input,
                keep_audio_input,
                device_input,
            ]

            # Bind events for live CLI command update
            for input_component in inputs:
                input_component.change(
                    fn=generate_command,
                    inputs=inputs,
                    outputs=command_output,
                )

            submit_btn.click(
                fn=run_v2t,
                inputs=inputs,
                outputs=[output_log, output_files],
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
                        headers=["发布时间", "标题", "作者"],
                        label="预览 (最多显示20条)",
                        wrap=True,
                    )

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
                outputs=[vlg_status, vlg_file, vlg_preview],
            )

if __name__ == "__main__":
    demo.launch(share=False)
