"""Render analysis.json into a self-contained HTML report.

Usage: python3 -m seo_report.build_report DATA_DIR OUT_HTML
"""
import json
import os
import sys

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "report_template.html")


def main():
    data_dir, out_html = sys.argv[1], sys.argv[2]
    with open(os.path.join(data_dir, "analysis.json"), encoding="utf-8") as f:
        analysis = json.load(f)
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()
    payload = json.dumps(analysis, ensure_ascii=False).replace("</", "<\\/")
    html = template.replace("/*__DATA__*/null", payload)
    os.makedirs(os.path.dirname(os.path.abspath(out_html)), exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out_html} ({len(html.encode('utf-8')) // 1024} KB)")


if __name__ == "__main__":
    main()
