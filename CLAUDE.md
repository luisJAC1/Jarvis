# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always read this file at the start of each session. Update the "Current Progress" and "Next Steps" sections when we finish something.**

---

## About Alfaro

- **Name:** Alfaro
- **OS:** Windows 11
- Main PC: SlateMeshI9N4701 (primary dev machine)
- Laptop: ASUS ROG with Kali Linux dual boot (used as local server)
- **Username:** ljalf

---

## Main Project: Jarvis

A general-purpose AI agent built in Python. The goal is an autonomous assistant that can handle tasks, respond to voice, and take real-world actions — think a personal Iron Man-style Jarvis.

**Current State:** Early prototype

### Tech Stack
- **AI brain:** Claude via the Anthropic SDK
- **Speech:** Whisper (speech-to-text) + pyttsx3 (text-to-speech)
- **Whatsapp Conection** Twilio 
- **Other tools:** Open to any open-source libraries that fit the job

---

## Alfaro's Preferences

- **Explain the why:** Always explain why a solution works, not just what it does
- **Prefer open source:** Default to open-source tools and libraries over paid/closed alternatives
- **Step-by-step:** Walk through changes before making them — no surprise rewrites
- **Ask before big changes:** Confirm the approach before touching important files or making structural decisions
- **Stay on track:** If I start going off-topic or down a rabbit hole, pull me back to the main goal
- **Session recap:** At the start of each session, give me a quick summary of where we left off
- **No over-engineering:** Keep solutions simple, I'm still learning — don't jump to complex patterns unnecessarily

---

## Current Progress

> _(Update this section at the end of each session)_

- Project is in early prototype stage
- Basic project structure being established

---

## Next Steps

> _(Update this section at the end of each session)_

- Define Jarvis's core loop (listen → think → respond → act)
- Set up the Anthropic SDK integration
- Get basic voice I/O working with Whisper + pyttsx3
