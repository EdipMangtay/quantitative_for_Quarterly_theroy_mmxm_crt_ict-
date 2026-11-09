#!/usr/bin/env python3
"""
ASTRA 6 V3.3 - Institutional HTML & PDF Report Generator.
Converts Markdown to publication-grade HTML and multi-page vector PDF via Chrome Headless.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
MD_PATH = ROOT / "reports" / "ASTRA6_V3_3_FINAL_NARRATIVE_RESEARCH.md"
HTML_PATH = ROOT / "reports" / "ASTRA6_V3_3_FINAL_NARRATIVE_RESEARCH.html"
PDF_PATH = ROOT / "reports" / "ASTRA6_V3_3_FINAL_NARRATIVE_RESEARCH.pdf"
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS_STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  --primary-color: #0f172a;
  --secondary-color: #1e3a8a;
  --accent-color: #2563eb;
  --text-main: #1e293b;
  --text-muted: #64748b;
  --bg-page: #f8fafc;
  --bg-card: #ffffff;
  --border-color: #e2e8f0;
}

* {
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  color: var(--text-main);
  background-color: var(--bg-page);
  margin: 0;
  padding: 30px 20px;
  line-height: 1.6;
  font-size: 14px;
}

.report-container {
  max-width: 1180px;
  margin: 0 auto;
  background: var(--bg-card);
  padding: 48px 56px;
  border-radius: 12px;
  box-shadow: 0 4px 25px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--border-color);
}

h1 {
  color: var(--primary-color);
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  border-bottom: 3px solid var(--accent-color);
  padding-bottom: 14px;
  margin-top: 0;
  margin-bottom: 12px;
  line-height: 1.25;
}

.report-subtitle {
  font-size: 15px;
  font-weight: 600;
  color: var(--secondary-color);
  margin-bottom: 24px;
}

.meta-header-box {
  background: #f1f5f9;
  border: 1px solid var(--border-color);
  border-left: 4px solid var(--accent-color);
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 32px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.meta-item {
  display: flex;
  flex-direction: column;
}

.meta-item .label {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 600;
  letter-spacing: 0.04em;
}

.meta-item .value {
  font-size: 14px;
  font-weight: 700;
  color: var(--primary-color);
  margin-top: 2px;
}

h2 {
  color: var(--secondary-color);
  font-size: 18px;
  font-weight: 700;
  margin-top: 36px;
  margin-bottom: 16px;
  border-left: 4px solid var(--accent-color);
  padding-left: 12px;
  letter-spacing: -0.01em;
}

h3 {
  color: var(--text-main);
  font-size: 15px;
  font-weight: 600;
  margin-top: 22px;
  margin-bottom: 10px;
}

p {
  margin: 10px 0 14px 0;
  line-height: 1.65;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 18px 0 24px 0;
  font-size: 11.5px;
  background: #ffffff;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow: hidden;
}

th {
  background: #1e293b;
  color: #ffffff;
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  font-size: 11.5px;
  letter-spacing: 0.02em;
}

td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-main);
}

tr:nth-child(even) td {
  background: #f8fafc;
}

tr:hover td {
  background: #f1f5f9;
}

pre {
  background: #0f172a;
  color: #f8fafc;
  padding: 14px 18px;
  border-radius: 8px;
  font-family: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  overflow-x: auto;
  line-height: 1.5;
  border: 1px solid #334155;
  margin: 16px 0 20px 0;
}

code {
  background: #e2e8f0;
  color: #0f172a;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11.5px;
}

pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  border-radius: 0;
}

blockquote {
  margin: 16px 0 20px 0;
  padding: 14px 20px;
  background: #eff6ff;
  border-left: 4px solid var(--accent-color);
  border-radius: 0 8px 8px 0;
  color: #1e3a8a;
  font-weight: 500;
}

blockquote p {
  margin: 0;
  font-size: 13.5px;
  color: #1e3a8a;
}

hr {
  border: 0;
  height: 1px;
  background: var(--border-color);
  margin: 32px 0;
}

ul, ol {
  margin: 10px 0 16px 20px;
  padding: 0;
}

li {
  margin-bottom: 6px;
  line-height: 1.6;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.badge-pass {
  background: #dcfce7;
  color: #166534;
}

.badge-fail {
  background: #fee2e2;
  color: #991b1b;
}

/* Print Specific Rules */
@media print {
  @page {
    size: A4 portrait;
    margin: 14mm 12mm 14mm 12mm;
  }
  body {
    background: #ffffff !important;
    padding: 0 !important;
    font-size: 9.5pt;
    color: #000000;
  }
  .report-container {
    max-width: 100% !important;
    padding: 0 !important;
    box-shadow: none !important;
    border: none !important;
  }
  h1 {
    font-size: 20pt;
    margin-bottom: 8px;
  }
  .report-subtitle {
    font-size: 11pt;
    margin-bottom: 16px;
  }
  h2 {
    break-before: page;
    page-break-before: always;
    margin-top: 0 !important;
    padding-top: 10px;
    font-size: 14pt;
    color: #1e3a8a !important;
    border-left: 4px solid #1e3a8a !important;
  }
  /* Avoid page break right after h1 */
  h2:first-of-type {
    page-break-before: avoid;
  }
  h3 {
    font-size: 11.5pt;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }
  p, li {
    font-size: 9.5pt;
    line-height: 1.5;
  }
  table {
    page-break-inside: avoid;
    font-size: 8pt !important;
    margin: 10px 0 16px 0;
  }
  th {
    background: #1e293b !important;
    color: #ffffff !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    padding: 5px 6px !important;
    font-size: 8pt !important;
  }
  td {
    padding: 4px 6px !important;
    font-size: 8pt !important;
  }
  pre {
    page-break-inside: avoid;
    font-size: 7.5pt !important;
    padding: 8px 12px !important;
    white-space: pre-wrap !important;
    word-break: break-all;
    background: #0f172a !important;
    color: #f8fafc !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  blockquote {
    page-break-inside: avoid;
    background: #eff6ff !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
    padding: 8px 14px !important;
    margin: 10px 0 !important;
  }
  tr {
    page-break-inside: avoid;
  }
}
"""

def build():
    print(f"Reading markdown from: {MD_PATH}")
    md_content = MD_PATH.read_text(encoding="utf-8")

    # Convert markdown body to html via pandoc
    cmd = [
        "pandoc",
        "--from=markdown",
        "--to=html5",
        "--no-highlight"
    ]
    proc = subprocess.run(cmd, input=md_content, text=True, capture_output=True, check=True)
    body_html = proc.stdout

    full_html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ASTRA 6 V3.3 — Nihai Fraktal Piyasa Anlatisi Raporu</title>
  <style>
{CSS_STYLES}
  </style>
</head>
<body>
  <div class="report-container">
    {body_html}
  </div>
</body>
</html>
"""

    HTML_PATH.write_text(full_html, encoding="utf-8")
    print(f"Wrote HTML report to: {HTML_PATH} ({len(full_html)} bytes)")

    # Render PDF via headless Chrome
    chrome_cmd = [
        CHROME_BIN,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        str(HTML_PATH)
    ]
    print(f"Executing Chrome Headless PDF generation...")
    res = subprocess.run(chrome_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Chrome error: {res.stderr}")
        sys.exit(res.returncode)

    print(f"Wrote PDF report to: {PDF_PATH}")

    # Inspect page count
    pg_proc = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", str(PDF_PATH)], capture_output=True, text=True)
    print(f"PDF Inspection: {pg_proc.stdout.strip()}")

if __name__ == "__main__":
    build()
