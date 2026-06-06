"""测试 aggregator._normalize_title — 标题归一化去重"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregator import _normalize_title


class TestNormalizeTitle(unittest.TestCase):
    """测试 _normalize_title"""

    def test_different_platform_suffixes_normalize_equal(self):
        """不同平台的同一标题归一化后应相等"""
        t1 = "某某高铁开通运营_新浪网"
        t2 = "某某高铁开通运营 - 知乎"
        self.assertEqual(_normalize_title(t1), _normalize_title(t2))

    def test_different_separators_normalize_equal(self):
        """不同分隔符的标题归一化后应相等"""
        t1 = "铁路安全通告_新浪新闻"
        t2 = "铁路安全通告｜新浪新闻"
        t3 = "铁路安全通告-新浪新闻"
        t4 = "铁路安全通告——新浪新闻"
        t5 = "铁路安全通告·新浪新闻"
        result = _normalize_title(t1)
        for t in [t2, t3, t4, t5]:
            self.assertEqual(_normalize_title(t), result)

    def test_no_suffix_unchanged_core(self):
        """无平台尾巴时核心内容应保留"""
        title = "某重要政策解读"
        norm = _normalize_title(title)
        self.assertIn("某重要政策解读", norm)

    def test_removes_punctuation(self):
        """标点符号应被去除"""
        title = "高铁，安全、第一！"
        norm = _normalize_title(title)
        self.assertNotIn("，", norm)
        self.assertNotIn("、", norm)
        self.assertNotIn("！", norm)

    def test_lowercase(self):
        """应转为小写"""
        title = "ABCD高铁"
        norm = _normalize_title(title)
        self.assertEqual(norm, norm.lower())

    def test_suffix_stripped(self):
        """常见平台尾巴应被剥离"""
        title = "某新闻标题_新浪财经"
        norm = _normalize_title(title)
        self.assertNotIn("新浪财经", norm)
        self.assertNotIn("新浪", norm)

    def test_multiple_suffixes(self):
        """多层平台尾巴都应被剥离"""
        title = "某文章_知乎专栏_新浪网"
        norm = _normalize_title(title)
        self.assertNotIn("知乎", norm)
        self.assertNotIn("新浪", norm)

    def test_long_suffix_matched_first(self):
        """更长后缀优先匹配，避免'新浪财经'被'新浪'误匹配"""
        # 假设有平台名叫 "财经"，如果短后缀先匹配，"新浪财经"会残留"新浪"
        # _PLATFORM_SUFFIXES 列表已按长度降序，"新浪财经"排在"新浪"前面
        title = "某报道_新浪财经"
        norm = _normalize_title(title)
        # "新浪财经" 作为一个整体应被剥离，不应残留"财经"
        # 归一化后应该是纯核心内容
        self.assertNotIn("新浪财经", norm)

    def test_empty_title(self):
        self.assertEqual(_normalize_title(""), "")

    def test_whitespace_only(self):
        self.assertEqual(_normalize_title("   "), "")

    def test_weibo_suffix(self):
        """微博相关尾巴应被剥离"""
        t1 = "热点新闻_微博正文"
        t2 = "热点新闻_微博"
        self.assertEqual(_normalize_title(t1), _normalize_title(t2))

    def test_toutiao_suffix(self):
        """头条相关尾巴应被剥离"""
        title = "某新闻-今日头条"
        norm = _normalize_title(title)
        self.assertNotIn("今日头条", norm)
        self.assertNotIn("头条", norm)

    def test_suffix_with_separator_space(self):
        """空格分隔的平台尾巴应能剥离"""
        title = "某标题 新浪网"
        norm = _normalize_title(title)
        self.assertNotIn("新浪网", norm)

    def test_suffix_without_separator_not_stripped(self):
        """无分隔符紧贴的汉字平台名不会被误剥（防止过度匹配）"""
        # "某标题新浪网" 中间没有空白分隔，正则要求 (?:\s+|^) 前置，
        # 所以尾部的"新浪网"不会被当作平台尾巴误删——这是正确的保守行为
        title = "某标题新浪网"
        norm = _normalize_title(title)
        self.assertIn("新浪网", norm)

    def test_suffix_mid_title_not_stripped(self):
        """标题中间的平台名不应被误删（仅剥离结尾）"""
        title = "新浪网发布新政策解读"
        norm = _normalize_title(title)
        self.assertIn("新浪网", norm)


if __name__ == "__main__":
    unittest.main()
