"""index.html の画像を埋め込み、1ファイルで表示できる共有用HTMLを作る。

使い方: python3 liberta-redesign/build_single.py
出力:   liberta-redesign/dist/liberta-design-comp.html
"""
import base64
import mimetypes
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index.html"
OUT = ROOT / "dist" / "liberta-design-comp.html"


def data_uri(rel: str) -> str:
    path = ROOT / rel
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def main() -> None:
    html = SRC.read_text(encoding="utf-8")
    cache: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        rel = m.group(2)
        cache.setdefault(rel, data_uri(rel))
        return f"{m.group(1)}{cache[rel]}{m.group(3)}"

    html = re.sub(r'(src=")(images/[^"]+)(")', repl, html)
    html = re.sub(r"(url\()(images/[^)]+)(\))", repl, html)
    # 埋め込んだ画像は遅延読み込みしない（PDF化・オフライン表示で確実に出すため）
    html = html.replace(' loading="lazy"', "")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT.parent)}: {len(cache)} images, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
