#!/usr/bin/env python3
"""Convert markdown wiki to HTML with auth check, with WIKI_PATH_MAP for link/label resolution."""

import sys, os, re

# ─────────────────────────────────────────────────────────────
# WIKI_PATH_MAP: short_name → (url_path, display_label)
# Every page in /opt/data/wiki/ must have an entry here.
# Missing entries = broken links and garbled labels in generated HTML.
# ─────────────────────────────────────────────────────────────
WIKI_PATH_MAP = {
    'gordon-rouse':           ('entities/gordon-rouse',           'Gordon Rouse'),
    'kla':                    ('entities/kla',                     'KLA'),
    'ventura-relocation':    ('concepts/ventura-relocation',      'Ventura Relocation'),
    'sidekick-studio':       ('projects/sidekick-studio',         'Sidekick Studio'),
    'hobbies/backcountry-fishing': ('hobbies/backcountry-fishing', 'Backcountry Fishing'),
    'hobbies/backpacking':    ('hobbies/backpacking',              'Backpacking'),
    'hobbies/hiking':         ('hobbies/hiking',                   'Hiking'),
    'hobbies/fitness':        ('hobbies/fitness',                  'Fitness'),
    'hobbies/personal-style':('hobbies/personal-style',           'Personal Style'),
    'hobbies/london-trip':    ('hobbies/london-trip',              'London Trip'),
    'log':                   ('log',                              'Log'),
}

def wiki_link(name):
    """Convert [[short_name]] markdown to a proper /wiki/ URL with display label."""
    name = name.replace('.md', '').replace('.html', '')
    if name in WIKI_PATH_MAP:
        path, label = WIKI_PATH_MAP[name]
    else:
        path = name
        label = name.split('/')[-1].replace('-', ' ').title()
    return f'<a href="/wiki/{path}">{label}</a>'

# ─────────────────────────────────────────────────────────────
# Markdown → HTML converter
# ─────────────────────────────────────────────────────────────
def md_to_html(text):
    lines = text.split('\n')
    html_lines = []
    in_code = False
    table_buf = []
    in_table = False

    def flush_table():
        if not table_buf:
            return ''
        rows = []
        for i, row in enumerate(table_buf):
            cells = [c.strip() for c in row.split('|') if c.strip()]
            tag = 'th' if (i == 0) else 'td'
            rows.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
        table_buf.clear()
        return '<table>' + ''.join(rows) + '</table>'

    for line in lines:
        if line.strip().startswith('```'):
            if in_table:
                html_lines.append(flush_table())
                in_table = False
            if not in_code:
                html_lines.append('<pre><code>')
                in_code = True
            else:
                html_lines.append('</code></pre>')
                in_code = False
            continue
        if in_code:
            html_lines.append(line)
            continue

        # Table rows
        if '|' in line and line.strip().startswith('|'):
            if line.strip() == '|' or set(line.strip().replace('-','').replace(':','').replace(' ','')) <= {'|'}:
                continue
            if not in_table:
                in_table = True
            table_buf.append(line)
            continue
        else:
            if in_table:
                html_lines.append(flush_table())
                in_table = False

        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            html_lines.append(f'<h{len(m.group(1))}>{m.group(2)}</h{len(m.group(1))}>')
            continue

        m = re.match(r'^[-*+]\s+(.*)', line)
        if m:
            html_lines.append(f'<li>{m.group(1)}</li>')
            continue

        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
        line = re.sub(r'`(.+?)`', r'<code>\1</code>', line)
        line = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', line)
        line = re.sub(r'\[\[([^\]]+)\]\]', lambda m: wiki_link(m.group(1)), line)
        if line.strip() in ('---', '***', '___'):
            html_lines.append('<hr>')
            continue
        if line.strip():
            html_lines.append(f'<p>{line}</p>')

    if in_table:
        html_lines.append(flush_table())

    return '\n'.join(html_lines)

# ─────────────────────────────────────────────────────────────
# HTML page builder with auth check
# ─────────────────────────────────────────────────────────────
def build_page(title, content_html, page_path):
    nav_items = [
        ('/wiki/',                 'Home'),
        ('/wiki/entities/gordon-rouse', 'Gordon'),
        ('/wiki/entities/kla',          'KLA'),
        ('/wiki/concepts/ventura-relocation', 'Ventura'),
        ('/wiki/projects/sidekick-studio',   'Sidekick'),
        ('/wiki/hobbies/backcountry-fishing', 'Fishing'),
        ('/wiki/hobbies/hiking',           'Hiking'),
        ('/wiki/hobbies/backpacking',      'Backpacking'),
        ('/wiki/hobbies/fitness',         'Fitness'),
        ('/wiki/hobbies/personal-style',   'Style'),
        ('/wiki/hobbies/london-trip',      'London'),
        ('/wiki/log',                     'Log'),
    ]
    active = '/' + page_path
    nav_html = '\n'.join(
        f'<li><a href="{href}" class="{"active" if active == href or (active.startswith(href) and href != "/wiki/") else ""}">{label}</a></li>'
        for href, label in nav_items
    )

    # Build the style block with PROPERLY DOUBLED BRACES for Python 3.13 f-string compatibility
    # All { and } in CSS must be {{ }} inside an f-string
    css_styles = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #0d1117; color: #e6edf3; line-height: 1.7; }
    a { color: #58a6ff; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .topbar { display: none; }
    .content { max-width: 900px; margin: 0 auto; padding: 40px 24px; }
    h1 { font-size: 28px; font-weight: 700; margin-bottom: 24px; border-bottom: 1px solid #30363d; padding-bottom: 16px; color: #58a6ff; }
    h2 { font-size: 20px; font-weight: 600; margin: 28px 0 12px; }
    h3 { font-size: 16px; font-weight: 600; margin: 20px 0 10px; color: #c9d1d9; }
    p { margin: 0 0 14px; }
    table { border-collapse: separate; border-spacing: 0; margin: 20px 0; width: 100%; font-size: 14px; border-radius: 8px; overflow: hidden; border: 1px solid #30363d; }
    th { background: #161b22; color: #8b949e; font-weight: 600; padding: 10px 14px; text-align: left; border-bottom: 1px solid #30363d; }
    td { padding: 10px 14px; border-bottom: 1px solid #21262d; }
    tr:last-child td { border-bottom: none; }
    tr:nth-child(even) td { background: #161b22; }
    tr:hover td { background: #1c2128; }
    code { background: #161b22; border: 1px solid #30363d; border-radius: 4px; padding: 1px 6px; font-size: 13px; font-family: monospace; }
    pre { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 16px 0; }
    pre code { border: none; padding: 0; background: none; }
    ul { margin: 0 0 14px 24px; }
    li { margin: 6px 0; }
    hr { border: none; border-top: 1px solid #30363d; margin: 28px 0; }
    blockquote { border-left: 3px solid #58a6ff; padding-left: 16px; color: #8b949e; margin: 16px 0; }
    """.replace('{', '{{').replace('}', '}}')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Gordon's Wiki</title>
  <style>
{css_styles}
  </style>
  <script>
    (function() {{
      var c = document.cookie.match(/wiki_auth=([^;]+)/);
      if (!c || c[1] !== 'GW2026') {{
        var dst = window.location.pathname;
        window.location.href = '/wiki/login?dst=' + encodeURIComponent(dst);
      }}
    }})();
  </script>
</head>
<body>
  <div class="topbar">
    <nav>
      <ul>
        {nav_html}
      </ul>
      <span class="wiki-label">Gordon's Wiki</span>
    </nav>
  </div>
  <div class="content">
    {content_html}
  </div>
</body>
</html>'''

def convert_file(md_path, base_dir, rel_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        end = content.find('\n---', 3)
        if end != -1:
            content = content[end+4:]
    title = 'Wiki'
    for line in content.split('\n'):
        m = re.match(r'^#\s+(.*)', line)
        if m:
            title = m.group(1)
            break
    html = md_to_html(content)
    out_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(build_page(title, html, rel_path.replace('\\','/').replace('.md','.html')))
    print(f'  {out_path}')

if __name__ == '__main__':
    wiki_dir = sys.argv[1] if len(sys.argv) > 1 else '/opt/data/wiki'
    base_out = '/opt/data/hermes-pages-repo/wiki'
    for root, dirs, files in os.walk(wiki_dir):
        for fn in files:
            if fn.endswith('.md'):
                md = os.path.join(root, fn)
                rel = os.path.relpath(md, wiki_dir)
                rel = rel.replace('index.md', 'index.html').replace('SCHEMA.md', 'schema.html').replace('log.md', 'log.html').replace('.md', '.html')
                convert_file(md, base_out, rel)