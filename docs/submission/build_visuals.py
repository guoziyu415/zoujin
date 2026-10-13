"""Render the public architecture image and editable SVG from the same drawing."""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render(output: Path, font_path: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1920, 1080), "#f3efe6")
    draw = ImageDraw.Draw(image)
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">', '<rect width="1920" height="1080" fill="#f3efe6"/>']

    def rect(box, fill, outline="#d9d2c3", radius=20):
        draw.rounded_rectangle(box, radius, fill=fill, outline=outline, width=2)
        x, y, x2, y2 = box
        svg.append(f'<rect x="{x}" y="{y}" width="{x2-x}" height="{y2-y}" rx="{radius}" fill="{fill}" stroke="{outline}" stroke-width="2"/>')

    def text(x, y, value, size=28, fill="#273b32"):
        font = ImageFont.truetype(font_path, size)
        draw.text((x, y), value, font=font, fill=fill)
        svg.append(f'<text x="{x}" y="{y+size}" font-family="Hiragino Sans,Hiragino Kaku Gothic ProN,Noto Sans JP,sans-serif" font-size="{size}" fill="{fill}">{html.escape(value)}</text>')

    def arrow(points, color="#927341", both=False):
        draw.line(points, fill=color, width=4, joint="curve")
        def head(a, b):
            theta = math.atan2(b[1]-a[1], b[0]-a[0])
            vertices = [b, (b[0]-15*math.cos(theta-0.5), b[1]-15*math.sin(theta-0.5)), (b[0]-15*math.cos(theta+0.5), b[1]-15*math.sin(theta+0.5))]
            draw.polygon(vertices, fill=color)
            svg.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in vertices)+f'" fill="{color}"/>')
        svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="4"/>')
        head(points[-2], points[-1])
        if both:
            head(points[1], points[0])

    text(70, 40, "zoujin", 56)
    text(70, 115, "会話と選択を、記憶と結末につなぐシステム", 34)
    text(1320, 70, "システムアーキテクチャ", 30)
    text(1320, 115, "現在の実装の主要経路  /  Google Cloud", 23, "#6d7569")

    rect((70, 225, 540, 445), "#ffffff")
    text(100, 252, "ブラウザ", 34)
    text(100, 310, "React・Three.js・WebAudio", 25)
    text(100, 350, "3D空間・字幕・テキスト入力", 25)
    text(100, 390, "書斎・記憶帳・因果マップ・回想録", 22)

    rect((710, 225, 1180, 445), "#e0e8df", "#9fac9d")
    text(740, 252, "Cloud Run  ゲートウェイ", 31)
    text(740, 310, "FastAPI・HTTPS / WebSocket", 25)
    text(740, 350, "サイトパスワード・招待セッション", 23)
    text(740, 390, "画面・資産配信 / 音声 / 状態通知", 23)

    rect((1340, 225, 1840, 445), "#273b32", "#273b32")
    text(1370, 252, "Cloud Run  叙事者", 32, "#f3efe6")
    text(1370, 310, "自作Pythonエージェント処理", 25, "#f3efe6")
    text(1370, 350, "意図抽出 → 規則・モデル検証", 25, "#f3efe6")
    text(1370, 390, "書き換え・拒否・確認 → 一括保存", 23, "#f3efe6")

    arrow([(540, 325), (710, 325)], both=True)
    text(558, 275, "HTTPS", 22)
    text(558, 365, "音声・差分", 21)
    arrow([(1180, 325), (1340, 325)])
    text(1194, 275, "IAM / OIDC", 21)
    text(1194, 365, "処理依頼", 21)

    rect((570, 575, 920, 745), "#ffffff")
    text(595, 602, "Gemini", 32)
    text(595, 660, "Live：人物の音声・字幕", 24)
    text(595, 700, "文字入力への人物応答", 24)
    arrow([(810, 445), (810, 530), (745, 530), (745, 575)], both=True)

    rect((990, 575, 1340, 745), "#ffffff")
    text(1015, 602, "Model Armor", 32)
    text(1015, 660, "入力・出力の安全チェック", 22)
    text(1015, 700, "安全判定を世界反映に連携", 21)
    arrow([(1100, 445), (1100, 530), (1165, 530), (1165, 575)], both=True)

    rect((1430, 575, 1840, 745), "#ffffff")
    text(1455, 602, "Claude", 32)
    text(1455, 660, "テキスト推論・事件抽出・叙述", 22)
    text(1455, 700, "検証・記憶・結末生成", 24)
    arrow([(1590, 445), (1590, 530), (1635, 530), (1635, 575)], both=True)

    rect((610, 820, 1840, 965), "#e0e8df", "#9fac9d")
    text(640, 842, "Cloud SQL  PostgreSQL", 31)
    text(640, 892, "処理キュー・世界状態・イベント・約束・人物記憶・結末・費用と失敗の指標", 25)
    arrow([(950, 445), (950, 820)], both=True)
    text(680, 778, "保存 / NOTIFY・LISTEN → 画面更新", 21)
    arrow([(1840, 350), (1880, 350), (1880, 890), (1840, 890)], both=True)

    rect((70, 820, 540, 965), "#ffffff")
    text(100, 842, "運用基盤", 29)
    text(100, 892, "Secret Manager / Artifact Registry", 23)
    text(100, 930, "秘密情報 / サービス共通イメージ", 21)
    text(70, 1002, "世界の変更は叙事者が検証して保存。生成された体験は原作本文と区別する。", 23)
    text(70, 1036, "音声はストリーミング。全音声の事前審査や、全会話の記憶成功を保証する構成ではありません。", 20, "#6d7569")
    image.save(output / "architecture.png", optimize=True)
    svg.append("</svg>")
    (output / "architecture.svg").write_text("\n".join(svg), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    render(args.output, args.font)
