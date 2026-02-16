# -*- coding: utf-8 -*-
# @file text_cleaner.py
# @brief Text Pre-processing and Noise Cleaning
# @author sailing-innocent
# @date 2026-02-16
# @version 1.0
# ---------------------------------
"""
文本预清理模块

功能：
1. 编码检测和统一转换为 UTF-8
2. 移除 URL 链接和广告内容
3. 清理乱码和格式错误
4. 标准化空白字符
5. 识别并标记可能的噪音段落
"""

import re
from typing import List, Tuple, Dict
from dataclasses import dataclass, field


@dataclass
class CleanResult:
    """清理结果"""
    cleaned_text: str
    removed_content: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    encoding: str = "utf-8"


class TextCleaner:
    """文本清理器"""
    
    # 正则表达式模式
    URL_PATTERN = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
        r'|www\.[^\s<>"{}|\\^`\[\]]+'
        r'|[a-zA-Z0-9.-]+\.(com|cn|net|org|io|cc|top|xyz)',
        re.IGNORECASE
    )
    
    EMAIL_PATTERN = re.compile(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    )
    
    # 广告关键词
    AD_PATTERNS = [
        re.compile(r'关注.*?(公众号|微信|微博|抖音|快手|B站)', re.IGNORECASE),
        re.compile(r'扫码.*?(加群|进群|关注)', re.IGNORECASE),
        re.compile(r'加入.*?QQ群[:：]?\s*\d+', re.IGNORECASE),
        re.compile(r'正版.*?订阅', re.IGNORECASE),
        re.compile(r'感谢.*?投推荐票', re.IGNORECASE),
        re.compile(r'求推荐|求收藏|求月票|求订阅', re.IGNORECASE),
        re.compile(r'本书首发于', re.IGNORECASE),
        re.compile(r'版权所有.*?转载', re.IGNORECASE),
        re.compile(r'VIP章节.*?阅读', re.IGNORECASE),
        re.compile(r'群号[:：]?\s*\d{5,}', re.IGNORECASE),
    ]
    
    # 纯符号行
    SYMBOL_PATTERN = re.compile(r'^[\s\-=\*#~\/\\|]{10,}$')
    
    # 分隔符行
    SEPARATOR_PATTERN = re.compile(r'^[\-=\*#~\/\\|]{3,}\s*[章节卷篇]?\s*[\-=\*#~\/\\|]{3,}$')
    
    # 乱码检测
    GARBAGE_PATTERN = re.compile(r'[锟斤拷烫屯臺毌]')
    
    # 连续空行
    MULTI_EMPTY_PATTERN = re.compile(r'\n{5,}')
    
    # 章节标题重复（用于检测标题在正文中重复出现）
    CHAPTER_REPEAT_PATTERN = re.compile(
        r'^(第[一二三四五六七八九十百千万零〇\d]+章.*?)$',
        re.MULTILINE
    )
    
    def __init__(self):
        self.removed_items = []
        self.warnings = []
    
    def clean(self, text: str, encoding: str = "utf-8") -> CleanResult:
        """
        执行文本清理
        
        Args:
            text: 原始文本
            encoding: 文本编码
            
        Returns:
            CleanResult: 清理结果
        """
        self.removed_items = []
        self.warnings = []
        
        original_length = len(text)
        
        # 1. 基础清理
        text = self._basic_clean(text)
        
        # 2. 移除 URL 和邮箱
        text = self._remove_urls(text)
        text = self._remove_emails(text)
        
        # 3. 移除广告内容
        text = self._remove_ads(text)
        
        # 4. 清理符号行
        text = self._clean_symbols(text)
        
        # 5. 标准化空白
        text = self._normalize_whitespace(text)
        
        # 6. 检测乱码
        text = self._detect_garbage(text)
        
        # 7. 生成警告
        self._generate_warnings(text, original_length)
        
        return CleanResult(
            cleaned_text=text,
            removed_content=self.removed_items,
            warnings=self.warnings,
            encoding=encoding
        )
    
    def _basic_clean(self, text: str) -> str:
        """基础清理：移除 NUL 字符，统一换行符"""
        # 移除 NUL 字符（PostgreSQL 不支持）
        text = text.replace('\x00', '')
        
        # 统一换行符为 \n
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # 移除 BOM
        if text.startswith('\ufeff'):
            text = text[1:]
            self.removed_items.append({
                "type": "bom",
                "content": "UTF-8 BOM header",
                "position": 0
            })
        
        return text
    
    def _remove_urls(self, text: str) -> str:
        """移除 URL 链接"""
        urls = self.URL_PATTERN.findall(text)
        if urls:
            for url in urls[:5]:  # 最多记录5个
                self.removed_items.append({
                    "type": "url",
                    "content": str(url)[:50],
                    "position": text.find(str(url)) if isinstance(url, str) else -1
                })
            text = self.URL_PATTERN.sub('', text)
        return text
    
    def _remove_emails(self, text: str) -> str:
        """移除邮箱地址"""
        emails = self.EMAIL_PATTERN.findall(text)
        if emails:
            for email in emails[:3]:
                self.removed_items.append({
                    "type": "email",
                    "content": email[:30],
                    "position": text.find(email)
                })
            text = self.EMAIL_PATTERN.sub('', text)
        return text
    
    def _remove_ads(self, text: str) -> str:
        """移除广告内容"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            is_ad = False
            for pattern in self.AD_PATTERNS:
                if pattern.search(line):
                    is_ad = True
                    self.removed_items.append({
                        "type": "ad",
                        "content": line[:80],
                        "line": i + 1
                    })
                    break
            
            if not is_ad:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _clean_symbols(self, text: str) -> str:
        """清理纯符号行"""
        lines = text.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            # 清理纯符号行
            if self.SYMBOL_PATTERN.match(line):
                self.removed_items.append({
                    "type": "symbols",
                    "content": line[:30],
                    "line": i + 1
                })
                continue
            
            # 清理分隔符行
            if self.SEPARATOR_PATTERN.match(line):
                self.removed_items.append({
                    "type": "separator",
                    "content": line[:30],
                    "line": i + 1
                })
                continue
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        # 将5个以上连续空行替换为2个
        text = self.MULTI_EMPTY_PATTERN.sub('\n\n', text)
        
        # 移除行尾空白
        lines = [line.rstrip() for line in text.split('\n')]
        
        # 移除连续的空行（超过2个）
        result_lines = []
        empty_count = 0
        for line in lines:
            if line == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def _detect_garbage(self, text: str) -> str:
        """检测并标记乱码"""
        garbage_matches = self.GARBAGE_PATTERN.findall(text)
        if garbage_matches:
            garbage_count = len(garbage_matches)
            self.warnings.append(
                f"检测到 {garbage_count} 处可能的乱码字符（如：锟斤拷、烫烫烫）"
            )
            # 尝试移除乱码字符
            text = self.GARBAGE_PATTERN.sub('', text)
        return text
    
    def _generate_warnings(self, text: str, original_length: int):
        """生成警告信息"""
        # 计算清理比例
        cleaned_length = len(text)
        removal_ratio = (original_length - cleaned_length) / original_length if original_length > 0 else 0
        
        if removal_ratio > 0.1:  # 清理超过10%
            self.warnings.append(
                f"清理移除了 {removal_ratio*100:.1f}% 的内容，请检查结果"
            )
        
        # 检测可能的编码问题
        if '�' in text:
            self.warnings.append("文本中包含替换字符(�)，可能存在编码问题")
        
        # 检测极短章节
        lines = [l for l in text.split('\n') if l.strip()]
        if len(lines) < 10 and len(text) < 1000:
            self.warnings.append("清理后文本极短，请检查源文件是否完整")
    
    def get_sample_text(self, text: str, sample_size: int = 3000, 
                       num_samples: int = 3) -> List[Tuple[int, str]]:
        """
        获取文本采样，用于AI分析
        
        Args:
            text: 原始文本
            sample_size: 每个采样的字符数
            num_samples: 采样数量（开头、中间、结尾）
            
        Returns:
            [(position, sample_text), ...]
        """
        text_length = len(text)
        samples = []
        
        if num_samples >= 1:
            # 开头采样
            start_sample = text[:sample_size]
            samples.append((0, start_sample))
        
        if num_samples >= 2 and text_length > sample_size * 3:
            # 中间采样
            mid_pos = text_length // 2 - sample_size // 2
            mid_sample = text[mid_pos:mid_pos + sample_size]
            samples.append((mid_pos, mid_sample))
        
        if num_samples >= 3 and text_length > sample_size * 2:
            # 结尾采样
            end_sample = text[-sample_size:]
            samples.append((text_length - sample_size, end_sample))
        
        return samples


def detect_encoding(file_path: str) -> Tuple[str, str]:
    """
    检测文件编码并读取内容
    
    Args:
        file_path: 文件路径
        
    Returns:
        (content, encoding)
    """
    encodings = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'gb2312', 'utf-16', 'big5']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    raise ValueError(f"无法解析文件编码: {file_path}")


def clean_file(file_path: str) -> CleanResult:
    """
    清理文件并返回结果
    
    Args:
        file_path: 文件路径
        
    Returns:
        CleanResult
    """
    content, encoding = detect_encoding(file_path)
    cleaner = TextCleaner()
    return cleaner.clean(content, encoding)


if __name__ == "__main__":
    # 简单测试
    test_text = """
第一章 测试章节

这是正文内容。

关注微信公众号获取最新章节
www.example.com

第二章 下一章
更多内容在这里。

==========

第三章
锟斤拷烫烫烫
    """
    
    cleaner = TextCleaner()
    result = cleaner.clean(test_text)
    
    print("清理后的文本：")
    print(result.cleaned_text)
    print("\n移除的内容：")
    for item in result.removed_content:
        print(f"  [{item['type']}] {item.get('content', '')[:40]}")
    print("\n警告：")
    for warning in result.warnings:
        print(f"  ! {warning}")
