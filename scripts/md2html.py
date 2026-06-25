#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2html.py — 艾利特文章富文本工具（可选，校验 / 清洗 / 兜底转换）

【定位】自写作提示词第十四节改为「直接产出富文本 HTML」后，模型正常情况下已直接
输出富文本 HTML，本脚本不再是主转换工具，而是可选的兜底 / 校验工具：

  1. 兜底转换：若模型偶发仍产出 Markdown（或拿到历史 MD 草稿），本脚本可把它转成
     富文本 HTML，结构与线上文章一致。
  2. 正文提取：从混合输入里只抽「正文 + 配图」部分，剔除 SEO 信息块、长尾词、
     内链建议、HTML 注释。

转换映射：
  ## 标题   -> <h2>标题</h2>
  ### 标题  -> <h3>标题</h3>
  普通段落  -> <p>...</p>
  ![alt](url) + 下一行 *图注*  -> <figure><img alt=... src=...><figcaption>图注</figcaption></figure>
  **加粗** -> <strong>加粗</strong>
  [锚文本](https://...) -> <a href="https://...">锚文本</a>
  Markdown 表格 -> <table><thead>...<tbody>...</table>
  *斜体图注独立行* -> <p><em>...</em></p>

只提取「正文 + 配图」部分（从首个图片或「## 文章内容」开始，到「## 内链建议」之前；
若无内链建议则到文末）。SEO 信息块、长尾词、内链建议清单不进 HTML（它们填 CMS 字段或
单独贴），避免污染正文。

用法：
  python scripts/md2html.py input.md            # 打印 HTML 到 stdout
  python scripts/md2html.py input.md -o out.html
  cat article.md | python scripts/md2html.py -  # 从 stdin 读

纯标准库，兼容 python 3.x，无需 pip 装包。
"""

import argparse
import re
import sys


def escape_html(text: str) -> str:
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))


def inline(text: str) -> str:
    """处理行内：链接、加粗、斜体（顺序很重要，先处理链接/加粗再转义其内部）。"""
    # 先用占位符提取链接和加粗，避免转义破坏其结构
    placeholders = []

    def stash(html_segment: str) -> str:
        token = f'\x00{len(placeholders)}\x00'
        placeholders.append(html_segment)
        return token

    # 链接 [text](url) —— 只认 http(s) 绝对链接，防误伤
    def repl_link(m):
        anchor = escape_html(m.group(1))
        url = m.group(2)
        return stash(f'<a href="{url}">{anchor}</a>')
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', repl_link, text)

    # 加粗 **x** 或 __x__
    def repl_bold(m):
        return stash(f'<strong>{escape_html(m.group(1))}</strong>')
    text = re.sub(r'\*\*([^\*]+)\*\__', repl_bold, text)
    text = re.sub(r'\*\*([^\*]+)\*\*', repl_bold, text)
    text = re.sub(r'__([^_]+)__', repl_bold, text)

    # 斜体 *x* 或 _x_（单个，且首尾紧贴非空白）—— 仅在整段是图注时由上层处理，
    # 行内零散斜体少见，这里保守不转，避免把列表 * 误判。

    # 转义剩余文本
    text = escape_html(text)

    # 还原占位符
    for i, seg in enumerate(placeholders):
        text = text.replace(f'\x00{i}\x00', seg)
    return text


TABLE_ROW = re.compile(r'^\s*\|(.+)\|\s*$')


def is_table_separator(line: str) -> bool:
    m = TABLE_ROW.match(line)
    if not m:
        return False
    cells = [c.strip() for c in m.group(1).split('|')]
    return all(re.fullmatch(r':?-{2,}:?', c) for c in cells) and any(c for c in cells)


def render_table(rows: list) -> str:
    """rows: list of cell-lists，第一行为表头。"""
    head = rows[0]
    body = rows[1:]
    out = ['<table>', '<thead><tr>']
    for c in head:
        out.append(f'<th>{inline(c.strip())}</th>')
    out.append('</tr></thead>')
    if body:
        out.append('<tbody>')
        for row in body:
            out.append('<tr>')
            for c in row:
                out.append(f'<td>{inline(c.strip())}</td>')
            out.append('</tr>')
        out.append('</tbody>')
    out.append('</table>')
    return '\n'.join(out)


def convert(md: str) -> str:
    lines = md.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    # ---- 1. 抽取正文区间 ----
    start = 0
    end = len(lines)
    have_start = False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not have_start and (s.startswith('## 文章内容') or s.startswith('![')):
            start = i
            # 如果锚定到 ## 文章内容，跳过该标题行本身
            if s.startswith('## 文章内容'):
                start = i + 1
            have_start = True
            break
    if not have_start:
        start = 0
    # 终点：内链建议 / 配图说明 注释块 之前
    stop_markers = ('## 内链建议', '<!-- 配图说明', '<!--配图说明')
    for j in range(start, len(lines)):
        if any(lines[j].strip().startswith(m) for m in stop_markers):
            end = j
            break
    body = lines[start:end]

    # 去掉首尾空白行
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()

    # ---- 2. 逐块转换 ----
    html = []
    i = 0
    n = len(body)
    while i < n:
        ln = body[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        # 跳过「长尾关键词拓展」等位于正文前的信息块残行（纯分隔线 ---）
        if s == '---':
            i += 1
            continue

        # HTML 注释直接跳过
        if s.startswith('<!--') :
            # 跳到注释结束
            while i < n and '-->' not in body[i]:
                i += 1
            i += 1
            continue

        # 标题
        m2 = re.match(r'^##\s+(.+)$', s)
        m3 = re.match(r'^###\s+(.+)$', s)
        m1 = re.match(r'^#\s+(.+)$', s)
        if m1:
            html.append(f'<h2>{inline(m1.group(1).strip())}</h2>')  # 正文不应有 H1，降级 h2
            i += 1
            continue
        if m3:
            html.append(f'<h3>{inline(m3.group(1).strip())}</h3>')
            i += 1
            continue
        if m2:
            title = m2.group(1).strip()
            # FAQ / 总结 等保留为 H2
            html.append(f'<h2>{inline(title)}</h2>')
            i += 1
            continue

        # 表格：连续 | 行 + 分隔行
        if TABLE_ROW.match(ln) and i + 1 < n and is_table_separator(body[i + 1]):
            rows = []
            while i < n and TABLE_ROW.match(body[i]):
                cells = [c for c in TABLE_ROW.match(body[i]).group(1).split('|')]
                rows.append(cells)
                i += 1
            # rows[0] 表头，rows[1] 是分隔行（丢弃），rows[2:] 是数据
            if len(rows) >= 2:
                rows = [rows[0]] + rows[2:]
                html.append(render_table(rows))
            continue

        # 图片：![alt](url)  +  可选下一行 *图注*
        m_img = re.match(r'^!\[([^\]]*)\]\((https?://[^\s)]+)\)\s*$', s)
        if m_img:
            alt = m_img.group(1)
            src = m_img.group(2)
            # 看下一行是否是斜体图注 *xxx* 或 _xxx_
            caption = ''
            if i + 1 < n:
                nxt = body[i + 1].strip()
                mc = re.match(r'^[\*_](.+)[\*_]$', nxt)
                if mc:
                    caption = mc.group(1)
                    i += 1  # 吃掉图注行
            fig = [f'<figure><img alt="{escape_html(alt)}" src="{src}">']
            if caption:
                fig.append(f'<figcaption>{inline(caption)}</figcaption>')
            fig.append('</figure>')
            html.append(''.join(fig))
            i += 1
            continue

        # 独立斜体图注行 *xxx*（前面没图也兜底转成 <p><em>）
        m_cap = re.match(r'^\*([^*]+)\*$', s)
        if m_cap:
            html.append(f'<p><em>{inline(m_cap.group(1))}</em></p>')
            i += 1
            continue

        # 有序列表 1. / 无序列表 - * +
        m_ol = re.match(r'^\d+\.\s+(.+)$', s)
        m_ul = re.match(r'^[-\*\+]\s+(.+)$', s)
        if m_ol or m_ul:
            tag = 'ol' if m_ol else 'ul'
            items = []
            pat = re.compile(r'^\d+\.\s+(.+)$') if m_ol else re.compile(r'^[-\*\+]\s+(.+)$')
            while i < n:
                mm = pat.match(body[i].strip())
                if not mm:
                    break
                items.append(f'<li>{inline(mm.group(1))}</li>')
                i += 1
            html.append(f'<{tag}>{"".join(items)}</{tag}>')
            continue

        # 普通段落（连续非空非结构行合并）
        para = [s]
        i += 1
        while i < n:
            nxt = body[i].strip()
            if (not nxt or nxt == '---'
                    or re.match(r'^#{1,6}\s', nxt)
                    or re.match(r'^!\[', nxt)
                    or re.match(r'^\d+\.\s', nxt)
                    or re.match(r'^[-\*\+]\s', nxt)
                    or (TABLE_ROW.match(body[i]) and i + 1 < n and is_table_separator(body[i + 1]))):
                break
            para.append(nxt)
            i += 1
        html.append(f'<p>{" ".join(inline(p) for p in para)}</p>')
        continue

    return '\n\n'.join(html)


def main():
    ap = argparse.ArgumentParser(description='把艾利特文章 Markdown 转成官网富文本 HTML')
    ap.add_argument('input', help='Markdown 文件路径，或 - 从 stdin 读')
    ap.add_argument('-o', '--output', help='输出 HTML 文件路径；不填则打印到 stdout')
    args = ap.parse_args()

    if args.input == '-':
        md = sys.stdin.read()
    else:
        with open(args.input, 'r', encoding='utf-8') as f:
            md = f.read()

    html = convert(md)
    out = html + '\n'
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(out)
    else:
        sys.stdout.write(out)


if __name__ == '__main__':
    main()
