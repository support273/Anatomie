# Social Media Collage Tool (4:5)

Dieses Skript erstellt automatisch Social-Media-Bilder im **4:5 Format** (z. B. 1080x1350):

- Ein Bild -> skaliert/zugeschnitten auf 4:5.
- Mehrere Bilder -> als Collage in einem 4:5-Endbild.
- Logo wird klein passend eingeblendet.
- Aus deinem Rohtext wird ein neuer deutscher Social-Text erzeugt.
- Zusätzlich wird ein kurzer viraler Titel erzeugt und direkt ins Bild gesetzt.
- Optional Versand des Bildes per Telegram.

## Installation

```bash
python -m pip install pillow requests
```

## Nutzung

```bash
python social_media_collage_tool.py \
  --images bild1.jpg bild2.jpg bild3.jpg \
  --logo logo.png \
  --text "Hier steht dein Rohtext ..." \
  --brand "Deine Marke" \
  --output final_post.jpg
```

## OpenAI (optional)

Wenn du echte KI-Umformulierung willst:

```bash
export OPENAI_API_KEY="dein_api_key"
```

Dann nutzt das Skript die OpenAI Responses API, sonst einen lokalen Fallback-Textgenerator.

## Telegram (optional)

```bash
python social_media_collage_tool.py \
  --images bild1.jpg bild2.jpg \
  --text "Rohtext" \
  --telegram-bot-token "<TOKEN>" \
  --telegram-chat-id "<CHAT_ID>"
```

Das Skript gibt den finalen Social-Text zusätzlich in der Konsole aus.
