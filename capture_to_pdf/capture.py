#!/usr/bin/env python3
"""
ブラウザで開いた資料ページを自動スクロールしながらスクリーンショットを撮り、
1つのPDFにまとめるツール。あわせてページ内のテキストも .md に書き出す。

使い方（詳しくは README.md）:
    python capture.py "https://資料のURL" -o 講座資料.pdf
"""

import argparse
import hashlib
import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

# ページ内で「一番大きいスクロール領域」を探して印を付ける。
# Notion などはページ全体ではなく内側の要素がスクロールするため。
FIND_SCROLLER_JS = """
() => {
  document.querySelectorAll('[data-capture-target]')
    .forEach(e => e.removeAttribute('data-capture-target'));
  let best = null, bestArea = 0;
  for (const el of document.querySelectorAll('*')) {
    const st = getComputedStyle(el);
    if (!/(auto|scroll|overlay)/.test(st.overflowY)) continue;
    if (el.scrollHeight - el.clientHeight < 50) continue;
    const r = el.getBoundingClientRect();
    const area = Math.max(0, r.width) * Math.max(0, r.height);
    if (area > bestArea) { best = el; bestArea = area; }
  }
  const doc = document.scrollingElement || document.documentElement;
  const docScrollable = doc.scrollHeight - window.innerHeight > 50;
  const viewArea = window.innerWidth * window.innerHeight;
  // ページ全体がスクロールできて、内側の領域が小さいならページ全体を使う
  if (!best || (docScrollable && bestArea < viewArea * 0.5)) return 'document';
  best.setAttribute('data-capture-target', '1');
  return 'element';
}
"""

SCROLL_JS = """
([mode, ratio]) => {
  const el = mode === 'document'
    ? (document.scrollingElement || document.documentElement)
    : document.querySelector('[data-capture-target]');
  const view = mode === 'document' ? window.innerHeight : el.clientHeight;
  const before = el.scrollTop;
  el.scrollTop = before + Math.floor(view * ratio);
  return [before, el.scrollTop];
}
"""

RESET_JS = """
(mode) => {
  const el = mode === 'document'
    ? (document.scrollingElement || document.documentElement)
    : document.querySelector('[data-capture-target]');
  el.scrollTop = 0;
}
"""

TEXT_JS = """
(mode) => {
  const el = mode === 'document' ? document.body
    : document.querySelector('[data-capture-target]');
  return el ? el.innerText : '';
}
"""


def capture_page(page, args, page_no):
    """現在表示中のページを上から下までスクショする。(画像リスト, テキスト) を返す"""
    mode = page.evaluate(FIND_SCROLLER_JS)
    print(f"  スクロール対象: {'ページ全体' if mode == 'document' else 'ページ内の領域'}")
    page.evaluate(RESET_JS, mode)
    time.sleep(args.wait)

    images, texts = [], []
    last_hash = None
    for step in range(args.max_steps):
        if mode == "element":
            box = page.locator("[data-capture-target]").bounding_box()
            vp = page.viewport_size
            x, y = max(box["x"], 0), max(box["y"], 0)
            clip = {
                "x": x,
                "y": y,
                "width": min(box["width"], vp["width"] - x),
                "height": min(box["height"], vp["height"] - y),
            }
            png = page.screenshot(clip=clip)
        else:
            png = page.screenshot()

        h = hashlib.md5(png).hexdigest()
        if h != last_hash:  # 見た目が変わらない撮影は捨てる
            images.append(Image.open(io.BytesIO(png)).convert("RGB"))
            last_hash = h
        texts.append(page.evaluate(TEXT_JS, mode))
        print(f"  撮影 {step + 1} 枚目", end="\r")

        before, after = page.evaluate(SCROLL_JS, [mode, args.overlap])
        if after <= before:  # これ以上スクロールできない = 最下部
            break
        time.sleep(args.wait)  # 遅延読み込みの画像などを待つ
    print(f"  {len(images)} 枚撮影しました        ")

    if args.save_png:
        d = Path(args.output).with_suffix("")
        d.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(images, 1):
            img.save(d / f"p{page_no:02d}_{i:03d}.png")
    return images, merge_texts(texts)


def merge_texts(texts):
    """スクロールごとに取ったテキストを、重複行を除いてつなげる"""
    out, seen = [], set()
    for t in texts:
        for line in t.splitlines():
            key = line.strip()
            if key and key in seen:
                continue
            seen.add(key)
            out.append(line)
    return "\n".join(out)


def save_pdf(images, path):
    images[0].save(path, save_all=True, append_images=images[1:], resolution=144)


def main():
    p = argparse.ArgumentParser(description="資料ページをスクロール撮影してPDFにまとめる")
    p.add_argument("url", help="最初に開くURL")
    p.add_argument("-o", "--output", default="capture.pdf", help="出力PDF名")
    p.add_argument("--width", type=int, default=1280, help="ブラウザの幅(px)")
    p.add_argument("--height", type=int, default=900, help="ブラウザの高さ(px)")
    p.add_argument("--wait", type=float, default=0.8, help="スクロール後の待ち秒数")
    p.add_argument("--overlap", type=float, default=0.85,
                   help="1回のスクロール量（画面の高さに対する割合。1未満で前の画像と少し重なる）")
    p.add_argument("--max-steps", type=int, default=300, help="1ページあたりの最大撮影枚数")
    p.add_argument("--channel", default=None,
                   help="'chrome' を指定するとPCにインストール済みのGoogle Chromeを使う")
    p.add_argument("--profile", default=".browser-profile",
                   help="ログイン状態を保存するフォルダ（次回からログイン不要）")
    p.add_argument("--save-png", action="store_true", help="PDFとは別にPNG画像も保存する")
    p.add_argument("--headless", action="store_true",
                   help="画面を出さずに実行（ログイン不要なページ向け）")
    p.add_argument("--no-prompt", action="store_true",
                   help="Enter待ちをせず、開いたページを1つだけ撮影して終了")
    p.add_argument("--executable-path", default=None, help=argparse.SUPPRESS)
    args = p.parse_args()

    all_images, all_texts = [], []
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            args.profile,
            headless=args.headless,
            channel=args.channel,
            executable_path=args.executable_path,
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=2,  # 文字をくっきり撮るため2倍解像度
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(args.url)

        page_no = 1
        while True:
            if not args.no_prompt:
                ans = input(
                    f"\n[{page_no}ページ目] ブラウザで撮りたい資料を表示してください。\n"
                    "  （初回はここでログイン）準備ができたら Enter / 終了は q + Enter: "
                ).strip().lower()
                if ans == "q":
                    break
            # 新しいタブで開いた場合に備え、最後のタブを対象にする
            page = ctx.pages[-1]
            page.bring_to_front()
            print(f"  撮影中: {page.title()}")
            imgs, text = capture_page(page, args, page_no)
            all_images += imgs
            all_texts.append(f"# {page.title()}\n\n{page.url}\n\n{text}\n")
            page_no += 1
            if args.no_prompt:
                break
        ctx.close()

    if not all_images:
        print("撮影した画像がないため、PDFは作成しませんでした。")
        return 1
    save_pdf(all_images, args.output)
    md = Path(args.output).with_suffix(".md")
    md.write_text("\n\n---\n\n".join(all_texts), encoding="utf-8")
    print(f"\n完了: {args.output}（{len(all_images)}ページ） と {md}（テキスト）を作成しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
