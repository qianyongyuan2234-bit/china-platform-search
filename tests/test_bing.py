"""测试 handlers/bing.py _clean_title 和 _parse_bing_results — 用假 HTML/脏标题（不发网络）"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.bing import _clean_title, _parse_bing_results


# 模拟 Bing CN 搜索结果 HTML
FAKE_BING_HTML = """
<ol id="b_results">
<li class="b_algo">
  <h2><a href="https://www.example.com/news/1">铁路安全工作会议在京召开</a></h2>
  <div class="b_caption">
    <p>近日，铁路系统安全工作会议在北京召开，部署了下一阶段重点工作任务。</p>
  </div>
</li>
<li class="b_algo">
  <h2><a href="https://zhihu.com/question/12345">高铁提速试验分析 - 知乎</a></h2>
  <div class="b_caption">
    <p>本文分析了中国高铁提速试验的数据和影响。</p>
  </div>
</li>
</ol>
"""

# 模拟含面包屑粘连的 Bing 标题 HTML
FAKE_BING_BREADCRUMB_HTML = """
<ol id="b_results">
<li class="b_algo">
  <h2><a href="https://baike.baidu.com/item/高铁">baidu.com › 高铁_百度百科</a></h2>
  <div class="b_caption">
    <p>高铁是指设计标准等级高、可供列车安全高速行驶的铁路系统。</p>
  </div>
</li>
</ol>
"""


class TestCleanTitle(unittest.TestCase):
    """测试 _clean_title"""

    def test_remove_embedded_url(self):
        """标题中嵌入的完整 URL 应被移除"""
        dirty = "baidu.comhttps://baike.baidu.com/item/高铁高铁百科"
        clean = _clean_title(dirty)
        self.assertNotIn("https://", clean)
        self.assertNotIn("baike.baidu.com", clean)

    def test_remove_breadcrumb_prefix(self):
        """面包屑前缀（domain › ）应被移除"""
        dirty = "baidu.com › 高铁_百度百科"
        clean = _clean_title(dirty)
        self.assertNotIn("baidu.com", clean)
        self.assertNotIn("›", clean)

    def test_collapse_whitespace(self):
        """多余空白应合并"""
        dirty = "高铁  安全  会议"
        clean = _clean_title(dirty)
        self.assertEqual(clean, "高铁 安全 会议")

    def test_clean_title_preserved(self):
        """正常标题应保持不变（去除空白外）"""
        clean = _clean_title("铁路安全工作会议")
        self.assertEqual(clean, "铁路安全工作会议")

    def test_strip_trailing_whitespace(self):
        """尾部空白应去除"""
        clean = _clean_title("  高铁新闻  ")
        self.assertEqual(clean, "高铁新闻")

    def test_empty_string(self):
        self.assertEqual(_clean_title(""), "")


class TestParseBingResults(unittest.TestCase):
    """测试 Bing 搜索结果解析"""

    def test_parse_basic_results(self):
        """基本解析：应能提取出 SearchResult"""
        results = _parse_bing_results(FAKE_BING_HTML, limit=10, pname="必应", domain=None)
        self.assertGreaterEqual(len(results), 1)
        r = results[0]
        self.assertIsNotNone(r.title)
        self.assertIsNotNone(r.url)
        self.assertIn("铁路", r.title)

    def test_parse_content_extracted(self):
        """段落的摘要内容应被提取"""
        results = _parse_bing_results(FAKE_BING_HTML, limit=10, pname="必应", domain=None)
        has_content = any(r.content for r in results)
        self.assertTrue(has_content)

    def test_domain_filter(self):
        """域名过滤：设置 domain 参数应只返回匹配域名的结果"""
        results = _parse_bing_results(
            FAKE_BING_HTML, limit=10, pname="必应", domain="zhihu.com"
        )
        # 只应返回 zhihu.com 的结果
        for r in results:
            self.assertIn("zhihu.com", r.url)
        self.assertGreaterEqual(len(results), 1)

    def test_domain_filter_excludes(self):
        """域名过滤应排除不匹配的结果"""
        results = _parse_bing_results(
            FAKE_BING_HTML, limit=10, pname="必应", domain="weibo.com"
        )
        # FAKE_BING_HTML 没有 weibo.com 的链接
        self.assertEqual(len(results), 0)

    def test_respects_limit(self):
        """limit 应生效"""
        results = _parse_bing_results(FAKE_BING_HTML, limit=1, pname="必应", domain=None)
        self.assertEqual(len(results), 1)

    def test_no_duplicate_urls(self):
        """不应有重复 URL"""
        results = _parse_bing_results(FAKE_BING_HTML, limit=10, pname="必应", domain=None)
        urls = [r.url for r in results]
        self.assertEqual(len(urls), len(set(urls)))

    def test_breadcrumb_title_cleaned(self):
        """含面包屑的标题应被清洗"""
        results = _parse_bing_results(
            FAKE_BING_BREADCRUMB_HTML, limit=10, pname="必应", domain=None
        )
        self.assertGreaterEqual(len(results), 1)
        r = results[0]
        # 标题不应包含 baidu.com 和 ›
        self.assertNotIn("baidu.com", r.title)
        self.assertNotIn("›", r.title)

    def test_title_no_html_tags(self):
        """标题不应包含 HTML 标签"""
        results = _parse_bing_results(FAKE_BING_HTML, limit=10, pname="必应", domain=None)
        for r in results:
            self.assertNotIn("<", r.title)
            self.assertNotIn(">", r.title)


if __name__ == "__main__":
    unittest.main()
