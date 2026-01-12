#!/usr/bin/env python
"""
vlg.py - Video List Getter
用途：使用 yt-dlp 获取作者/频道的视频列表，输出到 CSV 文件
支持平台：YouTube、Bilibili
"""
import argparse
import csv
import os
import re
import sys
import logging
import requests
import shutil
import tempfile
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class VideoEntry:
    """视频条目数据类"""

    upload_date: str
    title: str
    author: str
    url: str


class VideoListGetter:
    """视频列表获取器 - 使用 yt-dlp 获取频道/作者的视频列表"""

    def __init__(self, cookies_file: Optional[str] = None):
        """
        初始化视频列表获取器

        Args:
            cookies_file: cookies 文件路径 (Netscape 格式)
        """
        original_cookies = cookies_file or self._find_cookies_file()
        self.cookies_file = None
        self._temp_cookie_file = None

        if original_cookies and os.path.exists(original_cookies):
            try:
                # 创建临时副本以避免修改原始 cookies.txt
                fd, temp_path = tempfile.mkstemp(prefix="vlg_cookies_", suffix=".txt")
                os.close(fd)
                shutil.copy2(original_cookies, temp_path)
                self.cookies_file = temp_path
                self._temp_cookie_file = temp_path
                logger.debug(f"已创建临时 cookies 文件: {temp_path}")
            except Exception as e:
                logger.warning(f"创建临时 cookies 文件失败: {e}")
                self.cookies_file = original_cookies

    def cleanup(self):
        """清理临时文件"""
        if self._temp_cookie_file and os.path.exists(self._temp_cookie_file):
            try:
                os.remove(self._temp_cookie_file)
                logger.debug(f"已清理临时 cookies 文件: {self._temp_cookie_file}")
                self._temp_cookie_file = None
            except Exception as e:
                logger.warning(f"清理临时 cookies 文件失败: {e}")

    def __del__(self):
        self.cleanup()

    def _find_cookies_file(self) -> Optional[str]:
        """查找默认的 cookies.txt 文件"""
        default_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "cookies.txt"
        )
        if os.path.exists(default_path):
            return default_path
        return None

    def _get_ydl_opts(self, extract_flat: bool = True) -> dict:
        """
        获取 yt-dlp 配置选项

        Args:
            extract_flat: 是否只提取元数据不下载
        """
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": extract_flat,
            "ignoreerrors": True,
        }

        if self.cookies_file and os.path.exists(self.cookies_file):
            opts["cookiefile"] = self.cookies_file
            logger.info(f"使用 cookies 文件: {self.cookies_file}")

        return opts

    def detect_platform(self, url: str) -> str:
        """
        检测 URL 对应的平台

        Args:
            url: 频道/作者 URL

        Returns:
            平台名称: 'youtube', 'bilibili' 或 'unknown'
        """
        url_lower = url.lower()

        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
            return "bilibili"
        else:
            return "unknown"

    def normalize_channel_url(self, url: str) -> str:
        """
        规范化频道 URL，确保获取视频列表

        Args:
            url: 输入的频道 URL

        Returns:
            规范化后的 URL
        """
        platform = self.detect_platform(url)

        if platform == "youtube":
            # 处理 YouTube 频道 URL
            # 支持格式: /channel/xxx, /@username, /c/xxx, /user/xxx
            if "/videos" not in url:
                # 移除末尾斜杠
                url = url.rstrip("/")
                # 添加 /videos 后缀以获取视频列表
                url = url + "/videos"
            return url

        elif platform == "bilibili":
            # 处理 Bilibili 用户 URL
            # 格式: space.bilibili.com/uid 或 bilibili.com/space/uid
            # 提取用户 ID
            match = re.search(r"space\.bilibili\.com/(\d+)", url)
            if match:
                uid = match.group(1)
                # 返回用户投稿视频页面
                return f"https://space.bilibili.com/{uid}/video"

            match = re.search(r"bilibili\.com/space/(\d+)", url)
            if match:
                uid = match.group(1)
                return f"https://space.bilibili.com/{uid}/video"

            return url

        return url

    def parse_date_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        解析日期范围

        Args:
            start_date: 开始日期 (YYYY-MM-DD 格式)
            end_date: 结束日期 (YYYY-MM-DD 格式)
            days: 最近 N 天

        Returns:
            (开始日期, 结束日期) 元组
        """
        end_dt = None
        start_dt = None

        if days:
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days)
        else:
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    # 设置为当天结束
                    end_dt = end_dt.replace(hour=23, minute=59, second=59)
                except ValueError:
                    logger.warning(f"无效的结束日期格式: {end_date}")

            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"无效的开始日期格式: {start_date}")

        return start_dt, end_dt

    def _parse_upload_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        解析 yt-dlp 返回的上传日期

        Args:
            date_str: 日期字符串 (YYYYMMDD 格式)

        Returns:
            datetime 对象或 None
        """
        if not date_str:
            return None

        try:
            # yt-dlp 通常返回 YYYYMMDD 格式
            return datetime.strptime(str(date_str), "%Y%m%d")
        except ValueError:
            try:
                # 尝试其他常见格式
                return datetime.strptime(str(date_str), "%Y-%m-%d")
            except ValueError:
                return None

    def _format_date(self, date_str: Optional[str]) -> str:
        """
        格式化日期为可读格式

        Args:
            date_str: 原始日期字符串

        Returns:
            格式化后的日期字符串
        """
        if not date_str:
            return "未知"

        dt = self._parse_upload_date(date_str)
        if dt:
            return dt.strftime("%Y-%m-%d")
        return str(date_str)

    def _get_bilibili_uid(self, url: str) -> Optional[str]:
        """
        从 Bilibili URL 中提取用户 ID

        Args:
            url: Bilibili 用户空间 URL

        Returns:
            用户 ID 或 None
        """
        match = re.search(r"space\.bilibili\.com/(\d+)", url)
        if match:
            return match.group(1)

        match = re.search(r"bilibili\.com/space/(\d+)", url)
        if match:
            return match.group(1)

        return None

    def _get_bilibili_videos_via_ytdlp(
        self,
        url: str,
        max_videos: Optional[int] = None,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> List[VideoEntry]:
        """
        使用 yt-dlp 获取 Bilibili 用户投稿视频列表

        Args:
            url: 用户空间视频 URL
            max_videos: 最大视频数量
            start_dt: 开始日期过滤
            end_dt: 结束日期过滤

        Returns:
            VideoEntry 列表
        """
        import yt_dlp

        videos: List[VideoEntry] = []

        # 第一步：使用 flat 模式获取视频 ID 列表
        ydl_opts_flat = self._get_ydl_opts(extract_flat=True)
        if max_videos:
            ydl_opts_flat["playlistend"] = max_videos * 2

        video_ids = []
        channel_name = "未知"

        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            try:
                result = ydl.extract_info(url, download=False)
                if result:
                    channel_name = (
                        result.get("uploader")
                        or result.get("channel")
                        or result.get("title")
                        or "未知"
                    )
                    entries = result.get("entries", [])
                    for entry in entries:
                        if entry and entry.get("id"):
                            video_ids.append(entry.get("id"))
            except Exception as e:
                logger.error(f"获取视频列表失败: {e}")
                return videos

        if not video_ids:
            logger.warning("未找到视频")
            return videos

        print(f"📊 找到 {len(video_ids)} 个视频，正在获取详细信息...")

        # 第二步：逐个获取视频详细信息（非 flat 模式）
        ydl_opts_detail = self._get_ydl_opts(extract_flat=False)

        # 限制需要获取的视频数量
        target_count = max_videos if max_videos else len(video_ids)
        processed = 0

        with yt_dlp.YoutubeDL(ydl_opts_detail) as ydl:
            for video_id in video_ids:
                if len(videos) >= target_count:
                    break

                video_url = f"https://www.bilibili.com/video/{video_id}"

                try:
                    logger.debug(f"正在获取视频 {video_id} 的详细信息...")
                    info = ydl.extract_info(video_url, download=False)
                    if not info:
                        logger.debug(f"视频 {video_id} 信息为空，跳过")
                        continue

                    # 获取上传日期
                    upload_date_str = info.get("upload_date")
                    upload_dt = self._parse_upload_date(upload_date_str)

                    # 日期过滤
                    if upload_dt:
                        if start_dt and upload_dt < start_dt:
                            # 视频可能按时间排序，早于开始日期可以继续尝试
                            processed += 1
                            # 如果已经处理了很多但没找到符合条件的，可能需要继续
                            if processed > target_count * 2:
                                break
                            continue
                        if end_dt and upload_dt > end_dt:
                            continue

                    # 获取作者名称
                    author = info.get("uploader") or info.get("channel") or channel_name
                    logger.debug(
                        f"视频 {video_id} 作者: {author}, 标题: {info.get('title', '未知标题')}"
                    )

                    video = VideoEntry(
                        upload_date=self._format_date(upload_date_str),
                        title=info.get("title", "未知标题"),
                        author=author,
                        url=video_url,
                    )

                    videos.append(video)
                    processed += 1

                except Exception as e:
                    logger.debug(f"获取视频 {video_id} 信息失败: {e}")
                    continue

        # 按日期排序
        videos.sort(key=lambda x: x.upload_date, reverse=True)
        print(f"✅ 筛选后共 {len(videos)} 个视频")

        return videos

    def _get_bilibili_videos_via_api(
        self,
        uid: str,
        max_videos: Optional[int] = None,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> List[VideoEntry]:
        """
        使用第三方 uapis.cn API 获取用户投稿视频列表

        API 文档: https://uapis.cn/docs/api-reference/get-social-bilibili-archives

        Args:
            uid: 用户 ID (mid)
            max_videos: 最大视频数量
            start_dt: 开始日期过滤
            end_dt: 结束日期过滤

        Returns:
            VideoEntry 列表
        """
        import time

        videos: List[VideoEntry] = []
        page = 1
        page_size = 20  # uapis.cn 默认每页 20 条

        # uapis.cn API 端点
        api_url = "https://uapis.cn/api/v1/social/bilibili/archives"

        while True:
            params = {
                "mid": uid,
                "ps": page_size,
                "pn": page,
                "orderby": "pubdate",  # 按最新发布排序
            }

            try:
                response = requests.get(api_url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()

                # 检查错误响应 (400/404/500 等)
                if "code" in data:
                    error_code = data.get("code", "")
                    error_msg = data.get("message", "未知错误")
                    logger.warning(f"uapis.cn API 返回错误: [{error_code}] {error_msg}")
                    break

                # 解析响应数据
                video_list = data.get("videos", [])
                total = data.get("total", 0)

                if not video_list:
                    break

                for video_info in video_list:
                    # 解析发布时间（时间戳）
                    publish_ts = video_info.get("publish_time", 0)
                    if publish_ts:
                        upload_dt = datetime.fromtimestamp(publish_ts)
                        upload_date_str = upload_dt.strftime("%Y-%m-%d")
                    else:
                        upload_dt = None
                        upload_date_str = "未知"

                    # 日期过滤
                    if upload_dt:
                        if start_dt and upload_dt < start_dt:
                            # 由于按发布时间降序排列，如果当前视频早于开始日期，后面的更早，可以直接结束
                            return videos
                        if end_dt and upload_dt > end_dt:
                            continue

                    bvid = video_info.get("bvid", "")
                    video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""

                    # 注意: uapis.cn API 响应中没有 author 字段，需要从其他地方获取或留空
                    video = VideoEntry(
                        upload_date=upload_date_str,
                        title=video_info.get("title", "未知标题"),
                        author="",  # API 响应中未提供 author，后续可通过其他方式补充
                        url=video_url,
                    )

                    videos.append(video)

                    # 检查是否达到最大数量
                    if max_videos and len(videos) >= max_videos:
                        return videos

                # 检查是否还有更多页
                if page * page_size >= total:
                    break

                page += 1
                time.sleep(0.3)  # 分页请求间添加短暂延迟

            except requests.RequestException as e:
                logger.error(f"请求 uapis.cn API 失败: {e}")
                break
            except Exception as e:
                logger.error(f"解析 uapis.cn API 响应失败: {e}")
                break

        return videos

    def get_video_list(
        self,
        channel_url: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None,
        max_videos: Optional[int] = None,
    ) -> List[VideoEntry]:
        """
        获取频道/作者的视频列表

        Args:
            channel_url: 频道/作者 URL
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            days: 最近 N 天
            max_videos: 最大视频数量

        Returns:
            VideoEntry 列表
        """
        # 规范化 URL
        url = self.normalize_channel_url(channel_url)
        platform = self.detect_platform(url)

        print(f"📺 平台: {platform.upper()}")
        print(f"🔗 URL: {url}")
        print("⏳ 正在获取视频列表...")

        # 解析日期范围
        start_dt, end_dt = self.parse_date_range(start_date, end_date, days)

        if start_dt or end_dt:
            date_range_str = []
            if start_dt:
                date_range_str.append(f"从 {start_dt.strftime('%Y-%m-%d')}")
            if end_dt:
                date_range_str.append(f"到 {end_dt.strftime('%Y-%m-%d')}")
            print(f"📅 时间范围: {' '.join(date_range_str)}")

        videos: List[VideoEntry] = []

        # 对于所有平台，使用 yt-dlp
        try:
            import yt_dlp
        except ImportError:
            print("错误: yt-dlp 未安装")
            print("请运行: pip install yt-dlp")
            sys.exit(1)

        # 根据平台选择不同的获取方式
        if platform == "bilibili":
            # 对于 Bilibili，首先尝试使用 API 获取完整信息
            uid = self._get_bilibili_uid(channel_url)
            if uid:
                videos = self._get_bilibili_videos_via_api(
                    uid=uid,
                    max_videos=max_videos,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )
                if videos:
                    print(f"✅ 筛选后共 {len(videos)} 个视频")
                    return videos
                # 如果 API 失败，降级使用 yt-dlp（非 flat 模式）
                logger.info("API 获取失败，尝试使用 yt-dlp...")
                return self._get_bilibili_videos_via_ytdlp(
                    url=url,
                    max_videos=max_videos,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )

        # 获取视频列表
        ydl_opts = self._get_ydl_opts(extract_flat=True)

        # 设置最大下载数量（如果指定）
        if max_videos:
            ydl_opts["playlistend"] = max_videos * 2  # 留些余量用于日期过滤

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                result = ydl.extract_info(url, download=False)

                if not result:
                    logger.error("无法获取频道信息")
                    return videos

                # 获取频道名称
                channel_name = (
                    result.get("uploader")
                    or result.get("channel")
                    or result.get("title")
                    or "未知"
                )

                # 处理播放列表/频道中的视频
                entries = result.get("entries", [])

                if not entries:
                    # 如果没有 entries，可能是单个视频
                    if result.get("id"):
                        entries = [result]

                print(f"📊 找到 {len(entries) if entries else 0} 个视频")

                for entry in entries:
                    if not entry:
                        continue

                    # 获取上传日期
                    upload_date_str = entry.get("upload_date")
                    upload_dt = self._parse_upload_date(upload_date_str)

                    # 日期过滤
                    if upload_dt:
                        if start_dt and upload_dt < start_dt:
                            continue
                        if end_dt and upload_dt > end_dt:
                            continue

                    # 构建视频 URL
                    video_id = entry.get("id", "")
                    video_url = entry.get("url") or entry.get("webpage_url") or ""

                    if not video_url and video_id:
                        if platform == "youtube":
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                        elif platform == "bilibili":
                            video_url = f"https://www.bilibili.com/video/{video_id}"

                    # 获取作者名称
                    author = (
                        entry.get("uploader") or entry.get("channel") or channel_name
                    )

                    video = VideoEntry(
                        upload_date=self._format_date(upload_date_str),
                        title=entry.get("title", "未知标题"),
                        author=author,
                        url=video_url,
                    )

                    videos.append(video)

                    # 检查是否达到最大数量
                    if max_videos and len(videos) >= max_videos:
                        break

            except Exception as e:
                logger.error(f"获取视频列表失败: {e}")
                raise

        # 按日期排序（最新的在前）
        videos.sort(key=lambda x: x.upload_date, reverse=True)

        print(f"✅ 筛选后共 {len(videos)} 个视频")

        return videos

    def export_to_csv(
        self, videos: List[VideoEntry], output_path: str, encoding: str = "utf-8-sig"
    ) -> str:
        """
        将视频列表导出到 CSV 文件

        Args:
            videos: 视频列表
            output_path: 输出文件路径
            encoding: 文件编码 (默认 utf-8-sig 以支持 Excel)

        Returns:
            输出文件的绝对路径
        """
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 写入 CSV 文件
        with open(output_path, "w", newline="", encoding=encoding) as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow(["发布时间", "标题", "作者", "视频链接"])

            # 写入数据
            for video in videos:
                writer.writerow(
                    [video.upload_date, video.title, video.author, video.url]
                )

        abs_path = os.path.abspath(output_path)
        print(f"💾 已导出到: {abs_path}")

        return abs_path

    def run(
        self,
        channel_url: str,
        output: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None,
        max_videos: Optional[int] = None,
    ) -> tuple[List[VideoEntry], Optional[str]]:
        """
        运行视频列表获取流程

        Args:
            channel_url: 频道/作者 URL
            output: 输出文件路径
            start_date: 开始日期
            end_date: 结束日期
            days: 最近 N 天
            max_videos: 最大视频数量

        Returns:
            (视频列表, CSV文件路径) 元组
        """
        # 获取视频列表
        videos = self.get_video_list(
            channel_url=channel_url,
            start_date=start_date,
            end_date=end_date,
            days=days,
            max_videos=max_videos,
        )

        if not videos:
            print("⚠️ 未找到符合条件的视频")
            return videos, None

        # 生成默认输出路径
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"./output/video_list_{timestamp}.csv"

        # 导出到 CSV
        csv_path = self.export_to_csv(videos, output)

        return videos, csv_path


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="Video List Getter - 获取作者/频道的视频列表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取 YouTube 频道的所有视频
  python vlg.py https://www.youtube.com/@channel_name

  # 获取最近30天的视频
  python vlg.py https://www.youtube.com/@channel_name --days 30

  # 获取指定日期范围的视频
  python vlg.py https://www.youtube.com/@channel_name --start 2024-01-01 --end 2024-06-30

  # 获取 Bilibili 用户的视频
  python vlg.py https://space.bilibili.com/12345678

  # 指定输出文件
  python vlg.py https://www.youtube.com/@channel_name -o my_videos.csv
        """,
    )

    parser.add_argument("url", help="频道/作者 URL (支持 YouTube 和 Bilibili)")

    parser.add_argument(
        "-o",
        "--output",
        help="输出 CSV 文件路径 (默认: ./output/video_list_时间戳.csv)",
    )

    parser.add_argument("--start", help="开始日期 (YYYY-MM-DD 格式)")

    parser.add_argument("--end", help="结束日期 (YYYY-MM-DD 格式)")

    parser.add_argument(
        "--days", type=int, help="获取最近 N 天的视频 (与 --start/--end 互斥)"
    )

    parser.add_argument("--max", type=int, help="最大视频数量")

    parser.add_argument("--cookies", help="Cookies 文件路径 (Netscape 格式)")

    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 验证参数
    if args.days and (args.start or args.end):
        print("错误: --days 不能与 --start/--end 同时使用")
        sys.exit(1)

    print("=" * 60)
    print("📹 Video List Getter")
    print("=" * 60)

    # 创建获取器并运行
    getter = VideoListGetter(cookies_file=args.cookies)

    try:
        videos, csv_path = getter.run(
            channel_url=args.url,
            output=args.output,
            start_date=args.start,
            end_date=args.end,
            days=args.days,
            max_videos=args.max,
        )

        if videos:
            print("\n" + "=" * 60)
            print(f"✅ 完成! 共导出 {len(videos)} 个视频")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
    finally:
        if "getter" in locals():
            getter.cleanup()


if __name__ == "__main__":
    main()
