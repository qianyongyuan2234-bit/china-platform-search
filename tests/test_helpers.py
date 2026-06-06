"""测试 utils/helpers.py 中的纯函数"""
import unittest
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import clean_html, _normalize_href, _decode_url_query_param, _is_baidu_jump


class TestCleanHtml(unittest.TestCase):
    """测试 clean_html"""

    def test_remove_simple_tag(self):
        self.assertEqual(clean_html("<p>Hello</p>"), "Hello")

    def test_remove_nested_tags(self):
        self.assertEqual(clean_html("<div><span>text</span></div>"), "text")

    def test_remove_self_closing_tag(self):
        self.assertEqual(clean_html("before<br/>after"), "beforeafter")

    def test_remove_tag_with_attributes(self):
        self.assertEqual(
            clean_html('<a href="http://x.com" class="link">click</a>'),
            "click",
        )

    def test_no_tags_unchanged(self):
        self.assertEqual(clean_html("plain text"), "plain text")

    def test_empty_string(self):
        self.assertEqual(clean_html(""), "")

    def test_none_input(self):
        self.assertEqual(clean_html(None), "")

    def test_baidu_em_tag(self):
        """百度高亮标签 <em> 也应被去除"""
        self.assertEqual(clean_html("<em>关键词</em>"), "关键词")


class TestNormalizeHref(unittest.TestCase):
    """测试 _normalize_href"""

    def test_protocol_relative(self):
        self.assertEqual(
            _normalize_href("//www.baidu.com/link?url=xxx"),
            "https://www.baidu.com/link?url=xxx",
        )

    def test_path_relative(self):
        self.assertEqual(
            _normalize_href("/link?url=xxx"),
            "https://www.baidu.com/link?url=xxx",
        )

    def test_absolute_url(self):
        self.assertEqual(
            _normalize_href("https://example.com/page"),
            "https://example.com/page",
        )

    def test_empty_string(self):
        self.assertEqual(_normalize_href(""), "")

    def test_none_input(self):
        self.assertEqual(_normalize_href(None), "")

    def test_strips_whitespace(self):
        self.assertEqual(
            _normalize_href("  https://example.com  "),
            "https://example.com",
        )


class TestDecodeUrlQueryParam(unittest.TestCase):
    """测试 _decode_url_query_param"""

    def test_decode_url_param(self):
        result = _decode_url_query_param(
            "https://www.baidu.com/link?url=https%3A%2F%2Fexample.com%2Fpage"
        )
        self.assertEqual(result, "https://example.com/page")

    def test_no_url_param(self):
        self.assertIsNone(_decode_url_query_param("https://example.com/page"))

    def test_empty_url_param(self):
        self.assertIsNone(
            _decode_url_query_param("https://www.baidu.com/link?url=")
        )

    def test_non_http_url(self):
        """非 http(s) 的 URL 不会返回"""
        result = _decode_url_query_param(
            "https://www.baidu.com/link?url=ftp%3A%2F%2Ffiles.example.com"
        )
        self.assertIsNone(result)

    def test_exception_handled(self):
        """畸形 URL 不抛出异常"""
        result = _decode_url_query_param("not a url at all!!!")
        self.assertIsNone(result)


class TestIsBaiduJump(unittest.TestCase):
    """测试 _is_baidu_jump"""

    def test_baidu_link_url(self):
        self.assertTrue(
            _is_baidu_jump("http://www.baidu.com/link?url=xxx")
        )

    def test_baidu_link_path(self):
        self.assertTrue(_is_baidu_jump("https://www.baidu.com/link?url=xxx"))

    def test_simple_link_path(self):
        self.assertTrue(_is_baidu_jump("/link?url=xxx"))

    def test_non_baidu_url(self):
        self.assertFalse(_is_baidu_jump("https://example.com/page"))

    def test_empty_string(self):
        self.assertFalse(_is_baidu_jump(""))

    def test_none_input(self):
        self.assertFalse(_is_baidu_jump(None))


if __name__ == "__main__":
    unittest.main()
