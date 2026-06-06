"""测试 handlers/baidu.py _parse_baidu_results — 用假 HTML 验证解析（不发网络）"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.baidu import _parse_baidu_results


# 模拟百度移动端搜索结果 HTML（含 c-result 和 result 两种块）
FAKE_BAIDU_HTML = """
<html>
<body>
<div class="c-result">
  <h3 class="t">
    <a href="https://www.example.com/news/1">铁路安全工作会议在京召开</a>
  </h3>
  <div class="c-span-last">近日，铁路系统安全工作会议在北京召开，部署了下一阶段重点工作任务。</div>
</div>
<div class="result">
  <h3 class="t">
    <a href="https://weibo.com/u/1234567/status/abc123">高铁提速试验取得成功</a>
  </h3>
  <div class="c-abstract">中国铁路总公司宣布，新一代高铁提速试验取得圆满成功，最高时速突破400公里。</div>
</div>
</body>
</html>
"""

# 模拟无结果块的 HTML
FAKE_BAIDU_EMPTY = """
<html><body><p>没有找到相关内容</p></body></html>
"""

# 模拟带 protocol-relative 和 path-relative 链接的 HTML
FAKE_BAIDU_RELATIVE_LINKS = """
<html>
<body>
<div class="c-result">
  <h3 class="t">
    <a href="//m.baidu.com/link?url=abc">协议相对链接</a>
  </h3>
  <div class="c-span-last">摘要内容</div>
</div>
<div class="result">
  <h3 class="t">
    <a href="/s?word=test">路径相对链接</a>
  </h3>
  <div class="c-abstract">另一个摘要</div>
</div>
</body>
</html>
"""


class TestParseBaiduResults(unittest.TestCase):
    """测试百度搜索结果解析"""

    def test_parse_basic_results(self):
        """基本解析：应能提取出 SearchResult"""
        results = _parse_baidu_results(FAKE_BAIDU_HTML, limit=10, pname="百度")
        self.assertGreaterEqual(len(results), 1)
        # 第一个结果应有标题和 URL
        r = results[0]
        self.assertIsNotNone(r.title)
        self.assertIsNotNone(r.url)
        # 应该有 "铁路" 这个关键词
        self.assertIn("铁路", r.title)

    def test_parse_title_cleaned(self):
        """标题中的 HTML 标签应被清洗"""
        results = _parse_baidu_results(FAKE_BAIDU_HTML, limit=10, pname="百度")
        r = results[0]
        # 标题不应包含 HTML 标签
        self.assertNotIn("<", r.title)
        self.assertNotIn(">", r.title)
        self.assertNotIn("<em>", r.title)

    def test_parse_content_extracted(self):
        """摘要内容应被提取（c-span-last 或 c-abstract）"""
        results = _parse_baidu_results(FAKE_BAIDU_HTML, limit=10, pname="百度")
        # 至少一个结果有摘要
        has_content = any(r.content for r in results)
        self.assertTrue(has_content)

    def test_parse_respects_limit(self):
        """limit 参数应生效"""
        results = _parse_baidu_results(FAKE_BAIDU_HTML, limit=1, pname="百度")
        self.assertEqual(len(results), 1)

    def test_parse_empty_html(self):
        """空/无结果页面应返回空列表"""
        results = _parse_baidu_results(FAKE_BAIDU_EMPTY, limit=10, pname="百度")
        self.assertEqual(len(results), 0)

    def test_parse_platform_name(self):
        """platform 参数应写入结果"""
        results = _parse_baidu_results(FAKE_BAIDU_HTML, limit=10, pname="测试平台")
        for r in results:
            self.assertEqual(r.platform, "测试平台")

    def test_parse_protocol_relative_url(self):
        """protocol-relative URL（//开头）应补全为 https"""
        results = _parse_baidu_results(FAKE_BAIDU_RELATIVE_LINKS, limit=10, pname="百度")
        urls = [r.url for r in results]
        self.assertTrue(
            any(u.startswith("https://") for u in urls),
            f"应有 https:// 开头的 URL，实际: {urls}",
        )

    def test_parse_path_relative_url(self):
        """path-relative URL（/开头）应补全为 m.baidu.com"""
        results = _parse_baidu_results(FAKE_BAIDU_RELATIVE_LINKS, limit=10, pname="百度")
        urls = [r.url for r in results]
        full_urls = [u for u in urls if u.startswith("https://m.baidu.com")]
        self.assertTrue(
            len(full_urls) > 0,
            f"应有 m.baidu.com 开头的完整 URL，实际: {urls}",
        )

    def test_no_duplicate_urls(self):
        """不应返回重复 URL"""
        # 构造含重复链接的 HTML
        dup_html = """
        <div class="c-result">
          <h3 class="t"><a href="https://example.com/same">标题A</a></h3>
          <div class="c-span-last">摘要A</div>
        </div>
        <div class="result">
          <h3 class="t"><a href="https://example.com/same">标题B</a></h3>
          <div class="c-abstract">摘要B</div>
        </div>
        """
        results = _parse_baidu_results(dup_html, limit=10, pname="百度")
        urls = [r.url for r in results]
        self.assertEqual(len(urls), len(set(urls)))

    def test_skip_javascript_links(self):
        """javascript: 和 # 链接应被跳过"""
        js_html = """
        <div class="c-result">
          <h3 class="t"><a href="javascript:;">无效链接</a></h3>
          <div class="c-span-last">摘要</div>
        </div>
        <div class="result">
          <h3 class="t"><a href="#top">锚点链接</a></h3>
          <div class="c-abstract">摘要</div>
        </div>
        <div class="c-result">
          <h3 class="t"><a href="https://example.com/real">真实链接</a></h3>
          <div class="c-span-last">有效摘要</div>
        </div>
        """
        results = _parse_baidu_results(js_html, limit=10, pname="百度")
        urls = [r.url for r in results]
        self.assertEqual(len(urls), 1)
        self.assertIn("example.com", urls[0])


if __name__ == "__main__":
    unittest.main()
