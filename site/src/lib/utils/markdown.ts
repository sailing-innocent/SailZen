/**
 * @file markdown.ts
 * @brief Markdown -> HTML renderer (GitHub flavored style)
 * @author sailing-innocent
 * @date 2026-05-05
 *
 * 基于 markdown-it（GFM 表格/删除线）+ highlight.js 代码高亮 + DOMPurify 消毒。
 * 安全策略：markdown-it 关闭内嵌 HTML（html: false），渲染结果再过一遍
 * DOMPurify，防止 XSS。
 */

import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import DOMPurify from 'dompurify'

const md: MarkdownIt = new MarkdownIt({
  html: false, // 不解析 Markdown 中的内嵌 HTML，交由 DOMPurify 兜底
  linkify: true, // 自动识别链接
  typographer: true, // 智能标点
  breaks: false,
  highlight: (str: string, lang: string): string => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {
        // fall through to escaped plain text
      }
    }
    return md.utils.escapeHtml(str)
  },
})

// fence 渲染：给 <code> 加上 hljs class，使 highlight.js 主题样式生效
md.renderer.rules.fence = (tokens, idx): string => {
  const token = tokens[idx]
  const info = token.info ? String(token.info).trim() : ''
  const lang = info ? info.split(/\s+/g)[0] : ''
  const highlighted = md.options.highlight?.(token.content, lang, '') ?? ''
  const langClass = lang ? `hljs language-${lang}` : 'hljs'
  return `<pre><code class="${langClass}">${highlighted}\n</code></pre>\n`
}

/** 渲染 Markdown 为消毒后的 HTML 字符串 */
export function renderMarkdown(content: string): string {
  const html = md.render(content)
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

export default renderMarkdown
