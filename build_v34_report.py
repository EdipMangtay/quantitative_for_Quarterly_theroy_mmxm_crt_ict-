#!/usr/bin/env python3
"""
ASTRA 6 V3.4 - Institutional HTML & PDF Report Generator.
Converts reports/ASTRA6_V3_4_FINAL_VALIDATION.md to publication-grade HTML and multi-page vector PDF via Chrome Headless.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
MD_PATH = ROOT / "reports" / "ASTRA6_V3_4_FINAL_VALIDATION.md"
HTML_PATH = ROOT / "reports" / "ASTRA6_V3_4_FINAL_VALIDATION.html"
PDF_PATH = ROOT / "reports" / "ASTRA6_V3_4_FINAL_VALIDATION.pdf"
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

h2 {
  color: var(--secondary-color);
  font-size: 18px;
  font-weight: 700;
  border-bottom: 1.5px solid var(--border-color);
  padding-bottom: 8px;
  margin-top: 36px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

h3 {
  color: var(--primary-color);
  font-size: 15px;
  font-weight: 600;
  margin-top: 24px;
  margin-bottom: 12px;
}

p, li {
  color: var(--text-main);
  font-size: 13.5px;
  line-height: 1.65;
}

ul, ol {
  padding-left: 24px;
  margin-top: 8px;
  margin-bottom: 16px;
}

li {
  margin-bottom: 6px;
}

strong {
  color: #0f172a;
  font-weight: 600;
}

code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  color: #0f172a;
  border: 1px solid #e2e8f0;
}

pre {
  background: #0f172a;
  color: #f8fafc;
  padding: 16px 20px;
  border-radius: 8px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11.5px;
  line-height: 1.5;
  margin: 18px 0;
  border: 1px solid #1e293b;
}

pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  border: none;
  font-size: inherit;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  font-size: 12.5px;
  background: #ffffff;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

th {
  background: #f8fafc;
  color: var(--primary-color);
  font-weight: 600;
  text-align: left;
  padding: 10px 14px;
  border-bottom: 2px solid var(--border-color);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

td {
  padding: 9px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: var(--text-main);
}

tr:last-child td {
  border-bottom: none;
}

tr:nth-child(even) td {
  background-color: #fafbfc;
}

tr:hover td {
  background-color: #f1f5f9;
}

blockquote {
  border-left: 4px solid var(--accent-color);
  background: #eff6ff;
  padding: 12px 18px;
  margin: 18px 0;
  border-radius: 0 8px 8px 0;
  color: #1e3a8a;
  font-size: 13.5px;
}

blockquote p {
  margin: 0;
  color: #1e3a8a;
}

hr {
  border: none;
  border-top: 1px solid var(--border-color);
  margin: 32px 0;
}

@media print {
  body {
    background: #ffffff !important;
    padding: 0 !important;
  }
  .report-container {
    max-width: 100% !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: none !important;
  }
  h1 {
    font-size: 20pt !important;
    border-bottom: 2pt solid #2563eb !important;
  }
  h2 {
    font-size: 14pt !important;
    page-break-after: avoid;
    margin-top: 20pt !important;
  }
  h3 {
    font-size: 11pt !important;
    page-break-after: avoid;
  }
  p, li {
    font-size: 9.5pt !important;
    line-height: 1.5 !important;
  }
  table {
    page-break-inside: avoid;
    font-size: 8.5pt !important;
  }
  th, td {
    padding: 5pt 7pt !important;
  }
  pre {
    page-break-inside: avoid;
    font-size: 7.5pt !important;
    padding: 8pt 12pt !important;
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
    padding: 8pt 14pt !important;
    margin: 10pt 0 !important;
  }
  tr {
    page-break-inside: avoid;
  }
}
"""

def build():
    print(f"Reading markdown from: {MD_PATH}")
    md_content = MD_PATH.read_text(encoding="utf-8")

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
  <title>ASTRA 6 V3.4 — Nihai Strateji Dogrulama ve Uygulanabilir Islem Playbook Raporu</title>
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

    pg_proc = subprocess.run(["mdls", "-name", "kMDItemNumberOfPages", str(PDF_PATH)], capture_output=True, text=True)
    print(f"PDF Inspection: {pg_proc.stdout.strip()}")

if __name__ == "__main__":
    build()

