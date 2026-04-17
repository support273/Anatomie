#!/usr/bin/env python3
"""
Social Media Collage Tool (4:5)

Funktionen:
1) Ein oder mehrere Bilder in ein 4:5-Format (Standard 1080x1350) bringen.
   - Bei mehreren Bildern wird automatisch eine Collage erzeugt.
2) Logo klein und passend neben den Titel setzen.
3) Ausgangstext mit einer KI auf Deutsch neu formulieren (optional via OpenAI API).
4) Aus dem neuen Text einen viralen Titel erzeugen und direkt ins Bild schreiben.
5) Ergebnis als Bild exportieren und optional per Telegram senden.

Beispiel:
python social_media_collage_tool.py \
  --images bild1.jpg bild2.jpg bild3.jpg \
  --logo logo.png \
  --text "Hier steht dein Rohtext ..." \
  --output final_post.jpg \
  --brand "Anatomie" \
  --telegram-bot-token "$TELEGRAM_BOT_TOKEN" \
  --telegram-chat-id "$TELEGRAM_CHAT_ID"
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import random
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont


CANVAS_SIZE = (1080, 1350)  # 4:5


@dataclass
class GeneratedCopy:
    viral_title: str
    social_text: str


# ---------- Image helpers ----------
def fit_and_crop(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Skaliert ein Bild proportional und schneidet es mittig auf target_size."""
    tw, th = target_size
    iw, ih = image.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = image.resize((nw, nh), Image.Resampling.LANCZOS)

    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def rounded_rectangle_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def make_collage(images: Sequence[Image.Image], canvas_size: Tuple[int, int] = CANVAS_SIZE) -> Image.Image:
    """Erstellt eine optisch aufgeräumte Collage im 4:5 Format."""
    w, h = canvas_size
    canvas = Image.new("RGB", (w, h), "#111111")

    # Soft gradient background for nicer look
    bg = Image.new("RGB", (w, h), "#222222")
    bg_draw = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(24 + (42 - 24) * t)
        g = int(24 + (28 - 24) * t)
        b = int(30 + (56 - 30) * t)
        bg_draw.line((0, y, w, y), fill=(r, g, b))
    canvas.paste(bg)

    count = len(images)
    gap = 16
    margin = 28
    radius = 28

    # Basic aesthetically pleasing layouts up to 6 images, otherwise auto-grid
    if count == 1:
        slots = [(margin, margin, w - margin, h - margin)]
    elif count == 2:
        slots = [
            (margin, margin, w // 2 - gap // 2, h - margin),
            (w // 2 + gap // 2, margin, w - margin, h - margin),
        ]
    elif count == 3:
        slots = [
            (margin, margin, w - margin, (h * 2) // 3 - gap),
            (margin, (h * 2) // 3 + gap, w // 2 - gap // 2, h - margin),
            (w // 2 + gap // 2, (h * 2) // 3 + gap, w - margin, h - margin),
        ]
    elif count == 4:
        slots = [
            (margin, margin, w // 2 - gap // 2, h // 2 - gap // 2),
            (w // 2 + gap // 2, margin, w - margin, h // 2 - gap // 2),
            (margin, h // 2 + gap // 2, w // 2 - gap // 2, h - margin),
            (w // 2 + gap // 2, h // 2 + gap // 2, w - margin, h - margin),
        ]
    elif count == 5:
        top_h = int(h * 0.55)
        slots = [
            (margin, margin, w // 2 - gap // 2, top_h),
            (w // 2 + gap // 2, margin, w - margin, top_h),
            (margin, top_h + gap, (w - 2 * margin) // 3 + margin, h - margin),
            ((w - 2 * margin) // 3 + margin + gap, top_h + gap, 2 * (w - 2 * margin) // 3 + margin, h - margin),
            (2 * (w - 2 * margin) // 3 + margin + gap, top_h + gap, w - margin, h - margin),
        ]
    else:
        cols = 3
        rows = math.ceil(count / cols)
        cell_w = (w - 2 * margin - gap * (cols - 1)) // cols
        cell_h = (h - 2 * margin - gap * (rows - 1)) // rows
        slots = []
        for i in range(count):
            r = i // cols
            c = i % cols
            x1 = margin + c * (cell_w + gap)
            y1 = margin + r * (cell_h + gap)
            x2 = x1 + cell_w
            y2 = y1 + cell_h
            slots.append((x1, y1, x2, y2))

    for idx, box in enumerate(slots[:count]):
        x1, y1, x2, y2 = box
        slot_w, slot_h = x2 - x1, y2 - y1

        im = fit_and_crop(images[idx].convert("RGB"), (slot_w, slot_h))

        # subtle random micro-rotation for collage style
        angle = random.uniform(-1.2, 1.2)
        rot = im.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)

        mask = rounded_rectangle_mask((slot_w, slot_h), radius=radius)

        # Shadow
        shadow = Image.new("RGBA", (slot_w + 14, slot_h + 14), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((7, 7, slot_w + 7, slot_h + 7), radius=radius, fill=(0, 0, 0, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(7))
        canvas.paste(shadow.convert("RGB"), (x1 - 6, y1 - 4), shadow.split()[-1])

        canvas.paste(rot, (x1, y1), mask)

    return canvas


# ---------- Text / branding ----------
def try_load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    for fp in candidates:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size=size)
    return ImageFont.load_default()


def draw_title_with_logo(
    image: Image.Image,
    title: str,
    logo: Optional[Image.Image] = None,
    brand: str = "",
) -> Image.Image:
    draw = ImageDraw.Draw(image)
    w, h = image.size

    title_font = try_load_font(64, bold=True)
    brand_font = try_load_font(30, bold=False)

    wrapped = textwrap.fill(title.strip(), width=24)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=title_font, spacing=8)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x = 42
    pad_y = 30
    box_x1 = 40
    box_y1 = h - th - 250
    box_x2 = min(w - 40, box_x1 + tw + pad_x * 2 + 120)
    box_y2 = box_y1 + th + pad_y * 2 + 52

    # Glass-like panel for readability
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((box_x1, box_y1, box_x2, box_y2), radius=30, fill=(0, 0, 0, 145))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)

    text_x = box_x1 + pad_x
    text_y = box_y1 + pad_y

    # title outline
    for ox, oy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 2), (2, 0), (-2, 0), (0, -2)]:
        draw.multiline_text((text_x + ox, text_y + oy), wrapped, font=title_font, fill=(0, 0, 0), spacing=8)
    draw.multiline_text((text_x, text_y), wrapped, font=title_font, fill=(255, 255, 255), spacing=8)

    brand_text = brand.strip()
    if brand_text:
        brand_y = box_y2 - 50
        draw.text((text_x, brand_y), brand_text, font=brand_font, fill=(227, 227, 227))

    if logo is not None:
        logo = logo.convert("RGBA")
        max_logo_h = 56
        scale = min(1.0, max_logo_h / max(1, logo.height))
        lw = max(1, int(logo.width * scale))
        lh = max(1, int(logo.height * scale))
        logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)

        lx = box_x2 - lw - 28
        ly = box_y2 - lh - 22
        image.paste(logo, (lx, ly), logo)

    return image


# ---------- AI text generation ----------
def rewrite_with_ai_german(input_text: str, model: str = "gpt-4.1-mini") -> GeneratedCopy:
    """Nutzt OpenAI Responses API, wenn OPENAI_API_KEY gesetzt ist.
    Fallback: lokale einfache Umformulierung.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    cleaned = " ".join(input_text.split())

    if not cleaned:
        cleaned = "Spannender Beitrag mit nützlichen Erkenntnissen."

    if not api_key:
        return simple_local_rewrite(cleaned)

    prompt = (
        "Du bist ein Social-Media-Copywriter auf Deutsch. "
        "Formuliere den folgenden Rohtext in einen klaren, modernen Social-Post um (90-160 Wörter). "
        "Erzeuge zusätzlich einen kurzen viralen Titel (max. 8 Wörter). "
        "Gib ausschließlich JSON zurück mit den Schlüsseln: viral_title, social_text.\n\n"
        f"ROHTEXT:\n{cleaned}"
    )

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": prompt,
                "max_output_tokens": 500,
            },
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        text_out = extract_text_from_responses_api(data)

        parsed = json.loads(text_out)
        vt = (parsed.get("viral_title") or "Das solltest du heute wissen").strip()
        st = (parsed.get("social_text") or cleaned).strip()

        if len(vt) > 90:
            vt = vt[:87].rstrip() + "..."
        return GeneratedCopy(viral_title=vt, social_text=st)
    except Exception:
        return simple_local_rewrite(cleaned)


def extract_text_from_responses_api(payload: dict) -> str:
    # Try most common fields first
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    output = payload.get("output", [])
    chunks: List[str] = []
    for item in output:
        content = item.get("content", [])
        for c in content:
            if c.get("type") in {"output_text", "text"}:
                txt = c.get("text")
                if isinstance(txt, str) and txt.strip():
                    chunks.append(txt.strip())
    if chunks:
        return "\n".join(chunks)

    return json.dumps({"viral_title": "Mehr Reichweite mit diesem Trick", "social_text": ""})


def simple_local_rewrite(input_text: str) -> GeneratedCopy:
    """Fallback ohne API: simple heuristische Umformulierung auf Deutsch."""
    # crude sentence split
    sentences = [s.strip() for s in input_text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    key = sentences[:3]

    title_seed = key[0] if key else input_text
    words = title_seed.split()
    viral_title = " ".join(words[:7]).strip()
    if len(viral_title) < 12:
        viral_title = "Das musst du jetzt sehen"

    bullets = []
    for s in key:
        s = s[0].upper() + s[1:] if len(s) > 1 else s
        bullets.append(f"• {s}.")

    social_text = (
        "Hier ist die optimierte Version deines Beitrags:\n\n"
        + "\n".join(bullets)
        + "\n\nWenn dich das anspricht, speichere den Post und teile ihn mit jemandem, der das sehen sollte."
    )
    return GeneratedCopy(viral_title=viral_title, social_text=social_text)


# ---------- Telegram ----------
def send_to_telegram(image_path: Path, caption: str, bot_token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with image_path.open("rb") as f:
        files = {"photo": (image_path.name, f, "image/jpeg")}
        data = {"chat_id": chat_id, "caption": caption[:1024]}
        r = requests.post(url, files=files, data=data, timeout=45)
        r.raise_for_status()


# ---------- Main ----------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Erstellt 4:5 Social-Media-Bilder (Collage/Einzelbild) mit Text+Logo.")
    p.add_argument("--images", nargs="+", required=True, help="Pfad(e) zu Bilddateien")
    p.add_argument("--logo", default=None, help="Pfad zum Logo (optional)")
    p.add_argument("--text", required=True, help="Rohtext zur KI-Umformulierung")
    p.add_argument("--brand", default="", help="Kurzer Markenname unter dem Titel")
    p.add_argument("--output", default="social_post_4x5.jpg", help="Output-Datei")
    p.add_argument("--model", default="gpt-4.1-mini", help="OpenAI-Modell (wenn API-Key gesetzt)")
    p.add_argument("--telegram-bot-token", default=None, help="Telegram Bot Token (optional)")
    p.add_argument("--telegram-chat-id", default=None, help="Telegram Chat ID (optional)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    image_paths = [Path(p) for p in args.images]
    for p in image_paths:
        if not p.exists():
            raise FileNotFoundError(f"Bild nicht gefunden: {p}")

    images = [Image.open(p).convert("RGB") for p in image_paths]
    canvas = make_collage(images, CANVAS_SIZE)

    logo_img = None
    if args.logo:
        lp = Path(args.logo)
        if lp.exists():
            logo_img = Image.open(lp)

    generated = rewrite_with_ai_german(args.text, model=args.model)
    final = draw_title_with_logo(canvas, generated.viral_title, logo_img, brand=args.brand)

    out_path = Path(args.output)
    final.save(out_path, quality=95)

    print("=== FERTIG ===")
    print(f"Bild gespeichert: {out_path.resolve()}")
    print("\n--- Viral Titel ---")
    print(generated.viral_title)
    print("\n--- Social-Media-Text ---")
    print(generated.social_text)

    if args.telegram_bot_token and args.telegram_chat_id:
        send_to_telegram(out_path, generated.viral_title, args.telegram_bot_token, args.telegram_chat_id)
        print("\nBild wurde erfolgreich per Telegram versendet.")


if __name__ == "__main__":
    main()
