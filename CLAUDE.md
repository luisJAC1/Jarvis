# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always read this file at the start of each session. Update the "Current Progress" and "Next Steps" sections when we finish something.**

---

## About Alfaro

- **Name:** Alfaro
- **OS:** Windows 11
- **Main PC:** SlateMeshI9N4701 (primary dev machine)
- **Laptop:** ASUS ROG with Kali Linux dual boot (used as local server)
- **Username:** ljalf
- **Location:** Torreón, Coahuila, México (UTC-6)
- **GitHub:** luisJAC1

---

## Main Project: Jarvis

A personal AI assistant connected to WhatsApp. Jarvis can receive text, voice notes, and images, remember tasks and events across sessions, search the web, and (soon) send proactive reminders automatically.

**Current State:** Working WhatsApp bot, running locally with ngrok

### Tech Stack

| Layer | Technology |
|---|---|
| AI brain | Google Gemini 2.5 Flash via `google-genai` SDK |
| Web Search | Gemini built-in Google Search tool |
| WhatsApp | Twilio WhatsApp Sandbox |
| Memory | Google Sheets (`Memoria_Socio` spreadsheet) |
| Voice transcription | Gemini Files API |
| Image description | Gemini Files API |
| Web server | Flask + ngrok (local) → Railway (future) |
| Language | Python 3.14 |

### Why Gemini instead of Claude?
Anthropic billing wouldn't accept Alfaro's card. Gemini free tier works fine. The architecture is identical — swap the client and the plan is to migrate back to Claude later.

---

## File Structure

```
ClaudeCodeTest/
├── jarvis.py          — the entire bot (Flask webhook + AI + memory)
├── requirements.txt   — all dependencies
├── .env               — secrets (NOT committed, lives only on your machine)
├── .env.example       — template showing which vars are needed
├── .gitignore         — excludes .env, __pycache__
└── CLAUDE.md          — this file
```

---

## Architecture: How jarvis.py Works

### Request flow (every WhatsApp message)
```
WhatsApp message → Twilio → ngrok → Flask /bot endpoint
    ↓
Validate Twilio signature (reject fakes)
    ↓
Parse Body, NumMedia, MediaUrl0, MediaContentType0
    ↓
If media: download from Twilio (Basic Auth) → Gemini Files API → transcribe/describe
    ↓
Build mensaje_completo = media context + text body
    ↓
Load memory from Sheets (Perfil, Tareas, Eventos)
Load last 10 messages from Historial tab
    ↓
Build system prompt (personality + memory + rules injected dynamically)
    ↓
Call Gemini 2.5 Flash with Google Search tool + full conversation thread
    ↓
Parse GUARDAR: commands → write to Sheets
Parse ELIMINAR: commands → delete from Sheets
Parse RECORDAR: commands → write to Recordatorios tab (TODO — not yet implemented)
    ↓
Truncate response to 1580 chars at sentence boundary if needed
Save to Historial (truncated version — so Jarvis knows where it cut off)
    ↓
Return TwiML response to Twilio → WhatsApp
```

### Key design decisions
- **Conversation history is in Sheets, not in memory** — survives restarts
- **History saved AFTER truncation** — so "más" command works correctly
- **GUARDAR/ELIMINAR parsed on FULL text before truncation** — commands never get cut off
- **Singleton clients** — Sheets and Gemini clients created once, reused across requests
- **ProxyFix middleware** — required for ngrok/Railway reverse proxy (Twilio signature validation needs correct URL scheme)

---

## Google Sheets Structure (`Memoria_Socio`)

| Tab | Purpose | Key columns |
|---|---|---|
| Perfil | User profile, personality instructions, preferences | Single text column |
| Tareas | Pending tasks | Single text column |
| Eventos | Calendar events | Single text column |
| Historial | Conversation log | Role \| Message |
| Archivos | Media received (voice notes, images, docs) | Timestamp \| Type \| Name \| Description |
| Recordatorios | Scheduled reminders | Datetime (YYYY-MM-DD HH:MM) \| Mensaje \| Estado |

**Recordatorios tab** needs to be created manually (not yet done). `Estado` values: `pendiente` / `enviado`.

---

## Environment Variables (.env)

```
GEMINI_KEY=                    # Google AI Studio API key
GOOGLE_CREDS=                  # Full service account JSON (one line, no line breaks)
TWILIO_ACCOUNT_SID=            # From Twilio console
TWILIO_AUTH_TOKEN=             # From Twilio console
TWILIO_WA_NUMBER=whatsapp:+14155238886   # Twilio sandbox number
MI_NUMERO_WA=whatsapp:+5218717958181     # Alfaro's WhatsApp (single +, not ++)
GOOGLE_DRIVE_FOLDER_ID=        # Not actively used (Drive upload disabled — service account quota issue)
PORT=5000                      # Optional, defaults to 5000
```

**Service account email:** `socio-bot@socio-alfaro.iam.gserviceaccount.com`
This is the email used for Google Sheets access. It must have Editor access to the `Memoria_Socio` spreadsheet.

---

## How to Run Locally

```bash
# 1. Clone
git clone https://github.com/luisJAC1/Jarvis.git
cd Jarvis

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env from template and fill in all values
cp .env.example .env

# 4. Start the bot
python jarvis.py

# 5. In a second terminal, expose it to the internet
ngrok http 5000

# 6. Copy the https://...ngrok-free.app URL
# Go to Twilio console → WhatsApp Sandbox → "When a message comes in"
# Set to: https://YOUR-URL.ngrok-free.app/bot (POST)
```

**Test routes (browser):**
- `http://127.0.0.1:5000/test_sheets` — verify Sheets connection and show current memory

---

## System Prompt Summary

Jarvis's personality is built dynamically on every request. Key rules injected:
- **Language rule:** Always respond in the same language the user writes in (Spanish or English, never mixed)
- **Length limit:** Max 1500 chars. Offer to continue if complex. Resume from cutoff if user says "más"
- **Proactive:** Ask for missing details (date, time, platform) before saving a task
- **Personal context:** "Fer" = Fernanda (best friend). Don't re-ask things in history
- **Commands:** GUARDAR / ELIMINAR / RECORDAR (RECORDAR not yet fully implemented)
- **Personality override:** Alfaro can update personality via "GUARDAR: Perfil - Instrucción de Personalidad: ..."

---

## Current Progress

- ✅ WhatsApp bot working via Twilio + ngrok
- ✅ Gemini 2.5 Flash with Google Search tool
- ✅ Google Sheets memory (Perfil, Tareas, Eventos, Historial)
- ✅ GUARDAR / ELIMINAR command system
- ✅ Voice note transcription via Gemini Files API
- ✅ Image description via Gemini Files API
- ✅ Bilingual support (Spanish + English)
- ✅ Long response truncation at sentence boundary + "más" continuation
- ✅ History saved post-truncation (so continuation works correctly)
- ✅ Google Drive upload removed (service account quota issue — needs OAuth fix later)
- ✅ Repo on GitHub (private): https://github.com/luisJAC1/Jarvis
- ⏳ RECORDAR command system (designed, not yet coded)
- ⏳ Proactive reminders background thread (designed, not yet coded)

---

## Next Steps

1. **Proactive reminders system** — implement `RECORDAR:` command parsing + background thread that checks Recordatorios tab every 60 seconds and sends WhatsApp messages via Twilio REST API. Full design is already in the plan file.
2. **Deploy to Railway** — push repo, add env vars in Railway dashboard, update Twilio webhook to Railway URL
3. **Google Drive (fix)** — set up OAuth with user credentials instead of service account to enable file storage
4. **Archivos memory** — let Jarvis answer "qué archivos tengo?" by reading the Archivos Sheets tab
5. **Multi-media per message** — handle MediaUrl1, MediaUrl2, etc. (currently only handles first attachment)

---

## Alfaro's Preferences

- **Explain the why:** Always explain why a solution works, not just what it does
- **Prefer open source:** Default to open-source tools and libraries over paid/closed alternatives
- **Step-by-step:** Walk through changes before making them — no surprise rewrites
- **Ask before big changes:** Confirm the approach before touching important files or making structural decisions
- **Stay on track:** If I start going off-topic or down a rabbit hole, pull me back to the main goal
- **Session recap:** At the start of each session, give a quick summary of where we left off
- **No over-engineering:** Keep solutions simple, Alfaro is still learning — don't jump to complex patterns unnecessarily
