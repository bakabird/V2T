#!/usr/bin/env python
"""
vig.py - Video Info Getter CLI
用途：爬取 Bilibili 和 YouTube 视频的信息（上传作者、上传日期）
使用 Crawl4AI 进行网页爬取
"""
import argparse
import asyncio
import re
import sys
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs
from http.cookiejar import MozillaCookieJar

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """视频信息数据类"""

    platform: str
    video_id: str
    author: str
    upload_date: str
    title: Optional[str] = None
    url: Optional[str] = None


class VideoInfoGetter:
    """视频信息获取器"""

    # URL 模式匹配
    BILIBILI_PATTERNS = [
        r"bilibili\.com/video/(BV[\w]+)",
        r"bilibili\.com/video/(av\d+)",
        r"b23\.tv/([\w]+)",
    ]

    YOUTUBE_PATTERNS = [
        r"youtube\.com/watch\?v=([\w-]+)",
        r"youtu\.be/([\w-]+)",
        r"youtube\.com/shorts/([\w-]+)",
    ]

    def __init__(self):
        self.crawler = None
        self.cookies = self._load_cookies()

    def _load_cookies(self) -> list:
        """
        从 cookies.txt 文件加载 cookies（Netscape/Mozilla 格式）
        返回 Crawl4AI 所需的 cookies 列表格式
        """
        cookies_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "cookies.txt"
        )
        cookies = []

        if not os.path.exists(cookies_file):
            logger.debug("cookies.txt 文件不存在，将不使用 cookies")
            return cookies

        try:
            cookie_jar = MozillaCookieJar(cookies_file)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)

            for cookie in cookie_jar:
                cookies.append(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                        "secure": cookie.secure,
                    }
                )

            logger.info(f"成功从 cookies.txt 加载了 {len(cookies)} 个 cookies")
        except Exception as e:
            logger.warning(f"加载 cookies.txt 失败: {e}")

        return cookies

    def detect_platform(self, url: str) -> tuple[str, str]:
        """
        检测 URL 对应的平台和视频 ID
        返回: (platform, video_id)
        """
        # 检查 Bilibili
        for pattern in self.BILIBILI_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return "bilibili", match.group(1)

        # 检查 YouTube
        for pattern in self.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return "youtube", match.group(1)

        # 尝试从查询参数获取 YouTube video ID
        parsed = urlparse(url)
        if "youtube.com" in parsed.netloc:
            query_params = parse_qs(parsed.query)
            if "v" in query_params:
                return "youtube", query_params["v"][0]

        return "unknown", ""

    async def _init_crawler(self):
        """初始化 Crawl4AI 爬虫"""
        if self.crawler is None:
            try:
                from crawl4ai import AsyncWebCrawler, BrowserConfig

                # 配置浏览器，包含 cookies
                browser_config = BrowserConfig(
                    headless=True,
                    cookies=self.cookies if self.cookies else None,
                )
                self.crawler = AsyncWebCrawler(config=browser_config)
                await self.crawler.start()
            except ImportError:
                print("Error: crawl4ai not installed.")
                print("Please install it using: pip install crawl4ai")
                sys.exit(1)

    async def _close_crawler(self):
        """关闭爬虫"""
        if self.crawler:
            await self.crawler.close()
            self.crawler = None

    async def get_bilibili_info(self, video_id: str) -> Optional[VideoInfo]:
        """
        获取 Bilibili 视频信息
        """
        await self._init_crawler()

        url = f"https://www.bilibili.com/video/{video_id}"
        print(f"[Bilibili] 正在爬取: {url}")

        try:
            from crawl4ai import CrawlerRunConfig

            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=30000,
            )

            result = await self.crawler.arun(url=url, config=config)

            if not result.success:
                logger.error(f"爬取失败: {result.error_message}")
                return None

            html = result.html

            # 提取作者信息 - 从 meta 标签或页面内容中提取
            author = self._extract_bilibili_author(html)

            # 提取上传日期
            upload_date = self._extract_bilibili_date(html)

            # 提取标题
            title = self._extract_bilibili_title(html)

            return VideoInfo(
                platform="Bilibili",
                video_id=video_id,
                author=author or "未知",
                upload_date=upload_date or "未知",
                title=title,
                url=url,
            )

        except Exception as e:
            logger.error(f"获取 Bilibili 视频信息失败: {e}")
            return None

    def _extract_bilibili_author(self, html: str) -> Optional[str]:
        """从 Bilibili HTML 中提取作者"""
        patterns = [
            # meta 标签中的作者
            r'<meta\s+name="author"\s+content="([^"]+)"',
            # JSON-LD 数据中的作者
            r'"uploader":\s*{\s*"name":\s*"([^"]+)"',
            r'"owner":\s*{\s*[^}]*"name":\s*"([^"]+)"',
            # 页面元素中的作者名
            r'class="up-name[^"]*"[^>]*>([^<]+)<',
            r'class="username"[^>]*>([^<]+)<',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()

        # 尝试从 __INITIAL_STATE__ 中提取
        initial_state_match = re.search(
            r"__INITIAL_STATE__\s*=\s*({.*?});", html, re.DOTALL
        )
        if initial_state_match:
            try:
                data = json.loads(initial_state_match.group(1))
                if "videoData" in data and "owner" in data["videoData"]:
                    return data["videoData"]["owner"].get("name")
            except json.JSONDecodeError:
                pass

        return None

    def _extract_bilibili_date(self, html: str) -> Optional[str]:
        """从 Bilibili HTML 中提取上传日期"""
        patterns = [
            # 常见的日期格式
            r'"pubdate":\s*(\d+)',
            r'"ctime":\s*(\d+)',
            r'class="pubdate-text"[^>]*>([^<]+)<',
            r'class="pudate-text"[^>]*>([^<]+)<',
            # 页面中的日期显示
            r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})",
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
        ]

        for i, pattern in enumerate(patterns):
            match = re.search(pattern, html)
            if match:
                value = match.group(1)
                # 如果是时间戳，转换为日期
                if i < 2 and value.isdigit():
                    from datetime import datetime

                    try:
                        dt = datetime.fromtimestamp(int(value))
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                return value.strip()

        # 尝试从 __INITIAL_STATE__ 中提取
        initial_state_match = re.search(
            r"__INITIAL_STATE__\s*=\s*({.*?});", html, re.DOTALL
        )
        if initial_state_match:
            try:
                data = json.loads(initial_state_match.group(1))
                if "videoData" in data:
                    pubdate = data["videoData"].get("pubdate")
                    if pubdate:
                        from datetime import datetime

                        dt = datetime.fromtimestamp(int(pubdate))
                        return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    def _extract_bilibili_title(self, html: str) -> Optional[str]:
        """从 Bilibili HTML 中提取标题"""
        patterns = [
            r"<title>([^<]+)</title>",
            r'<meta\s+property="og:title"\s+content="([^"]+)"',
            r'"title":\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                title = match.group(1).strip()
                # 清理 Bilibili 标题后缀
                title = re.sub(r"_哔哩哔哩_bilibili$", "", title)
                title = re.sub(r"-哔哩哔哩$", "", title)
                return title

        return None

    async def get_youtube_info(self, video_id: str) -> Optional[VideoInfo]:
        """
        获取 YouTube 视频信息
        """
        await self._init_crawler()

        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[YouTube] 正在爬取: {url}")

        try:
            from crawl4ai import CrawlerRunConfig

            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=30000,
            )

            result = await self.crawler.arun(url=url, config=config)

            if not result.success:
                logger.error(f"爬取失败: {result.error_message}")
                return None

            html = result.html

            # 提取作者信息
            author = self._extract_youtube_author(html)

            # 提取上传日期
            upload_date = self._extract_youtube_date(html)

            # 提取标题
            title = self._extract_youtube_title(html)

            return VideoInfo(
                platform="YouTube",
                video_id=video_id,
                author=author or "未知",
                upload_date=upload_date or "未知",
                title=title,
                url=url,
            )

        except Exception as e:
            logger.error(f"获取 YouTube 视频信息失败: {e}")
            return None

    def _extract_youtube_author(self, html: str) -> Optional[str]:
        """从 YouTube HTML 中提取作者"""
        patterns = [
            # JSON-LD 数据
            r'"author":\s*"([^"]+)"',
            r'"ownerChannelName":\s*"([^"]+)"',
            r'"channelName":\s*"([^"]+)"',
            # meta 标签
            r'<link\s+itemprop="name"\s+content="([^"]+)"',
            r'"name":\s*"([^"]+)"[^}]*"@type":\s*"Person"',
            # ytInitialData 中的数据
            r'"videoOwnerRenderer"[^}]*"title"[^}]*"runs"[^}]*"text":\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()

        # 尝试从 ytInitialPlayerResponse 中提取
        player_response_match = re.search(
            r"ytInitialPlayerResponse\s*=\s*({.*?});", html, re.DOTALL
        )
        if player_response_match:
            try:
                # 简单提取 author 字段
                author_match = re.search(
                    r'"author":\s*"([^"]+)"', player_response_match.group(1)
                )
                if author_match:
                    return author_match.group(1)
            except:
                pass

        return None

    def _extract_youtube_date(self, html: str) -> Optional[str]:
        """从 YouTube HTML 中提取上传日期"""
        patterns = [
            # JSON 数据中的日期
            r'"uploadDate":\s*"([^"]+)"',
            r'"publishDate":\s*"([^"]+)"',
            r'"dateText"[^}]*"simpleText":\s*"([^"]+)"',
            # meta 标签
            r'<meta\s+itemprop="uploadDate"\s+content="([^"]+)"',
            r'<meta\s+itemprop="datePublished"\s+content="([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                date_str = match.group(1).strip()
                # 尝试格式化日期
                try:
                    from datetime import datetime

                    # 尝试解析 ISO 格式
                    if "T" in date_str:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        return dt.strftime("%Y-%m-%d")
                except:
                    pass
                return date_str

        return None

    def _extract_youtube_title(self, html: str) -> Optional[str]:
        """从 YouTube HTML 中提取标题"""
        patterns = [
            r'<meta\s+property="og:title"\s+content="([^"]+)"',
            r"<title>([^<]+)</title>",
            r'"title":\s*"([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                title = match.group(1).strip()
                # 清理 YouTube 标题后缀
                title = re.sub(r"\s*-\s*YouTube$", "", title)
                return title

        return None

    async def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """
        根据 URL 自动识别平台并获取视频信息
        """
        platform, video_id = self.detect_platform(url)

        if platform == "bilibili":
            return await self.get_bilibili_info(video_id)
        elif platform == "youtube":
            return await self.get_youtube_info(video_id)
        else:
            logger.error(f"无法识别的视频平台: {url}")
            return None

    async def process_urls(self, urls: list[str], output_format: str = "text"):
        """
        批量处理视频 URL
        """
        results = []

        try:
            for url in urls:
                info = await self.get_video_info(url)
                if info:
                    results.append(info)
                print("-" * 50)
        finally:
            await self._close_crawler()

        # 输出结果
        self._output_results(results, output_format)

        return results

    def _output_results(self, results: list[VideoInfo], output_format: str):
        """输出结果"""
        if not results:
            print("\n没有获取到任何视频信息。")
            return

        print("\n" + "=" * 60)
        print("📹 视频信息汇总")
        print("=" * 60)

        if output_format == "json":
            import json

            data = [
                {
                    "platform": r.platform,
                    "video_id": r.video_id,
                    "author": r.author,
                    "upload_date": r.upload_date,
                    "title": r.title,
                    "url": r.url,
                }
                for r in results
            ]
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            for i, info in enumerate(results, 1):
                print(f"\n[{i}] {info.platform}")
                if info.title:
                    print(f"    标题: {info.title}")
                print(f"    作者: {info.author}")
                print(f"    上传日期: {info.upload_date}")
                print(f"    视频ID: {info.video_id}")
                if info.url:
                    print(f"    链接: {info.url}")


def main():
    parser = argparse.ArgumentParser(
        description="Video Info Getter - 获取 Bilibili/YouTube 视频信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python vig.py https://www.bilibili.com/video/BV1xx411c7mD
  python vig.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
  python vig.py url1 url2 url3 --format json
  python vig.py urls.txt
        """,
    )

    parser.add_argument(
        "urls", nargs="+", help="视频 URL 或包含 URL 列表的文本文件路径"
    )
    parser.add_argument(
        "-f",
        "--format",
        default="text",
        choices=["text", "json"],
        help="输出格式 (默认: text)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 处理输入的 URL
    urls = []
    import os

    for url_arg in args.urls:
        if os.path.isfile(url_arg):
            with open(url_arg, "r", encoding="utf-8") as f:
                urls.extend(
                    [
                        line.strip()
                        for line in f
                        if line.strip() and not line.startswith("#")
                    ]
                )
        else:
            urls.append(url_arg)

    if not urls:
        print("错误: 未提供任何有效的视频 URL")
        sys.exit(1)

    print(f"📋 共 {len(urls)} 个视频待处理\n")

    # 创建获取器并处理
    getter = VideoInfoGetter()
    asyncio.run(getter.process_urls(urls, args.format))


if __name__ == "__main__":
    main()
