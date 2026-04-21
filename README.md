# Jarvis — Personal WhatsApp AI Assistant

A personal AI assistant that lives in WhatsApp, powered by Google Gemini. Send a message, get an intelligent response. Built for real daily use — reminders, tasks, questions, and more.

---

## Features

- **WhatsApp Integration** — Chat with your AI assistant directly from WhatsApp
- **Powered by Gemini** — Google's latest LLM for smart, context-aware responses
- **Task & Reminder Support** — Ask Jarvis to remember things, set reminders, and manage your day
- **Fast & Lightweight** — Simple Python architecture, easy to deploy and run
- **Secure by Design** — API keys managed via environment variables, never hardcoded

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core language |
| Google Gemini API | AI language model |
| WhatsApp Business API | Messaging interface |
| python-dotenv | Environment variable management |

---

## Getting Started

### Prerequisites

- Python 3.9+
- A WhatsApp Business API account
- A Google Gemini API key

### Installation

```bash
# Clone the repository
git clone https://github.com/luisJAC1/Jarvis.git
cd Jarvis

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Open `.env` and fill in your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key_here
WHATSAPP_TOKEN=your_whatsapp_token_here
PHONE_NUMBER_ID=your_phone_number_id_here
```

### Run

```bash
python jarvis.py
```

---

## Project Structure

```
Jarvis/
├── jarvis.py          # Main application logic
├── requirements.txt   # Python dependencies
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
└── CLAUDE.md          # AI assistant context file
```

---

## Roadmap

- [ ] Voice message support
- [ ] Memory persistence across conversations
- [ ] Calendar integration
- [ ] Multi-language support (English/Spanish)
- [ ] Claude API integration (Anthropic)

---

## Author

**Luis Alfaro** — LegalTech AI Developer  
Upwork: https://www.upwork.com/freelancers/~luisalfaro  
GitHub: https://github.com/luisJAC1

---

## License

MIT License — feel free to use and modify for your own projects.
