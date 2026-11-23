# AI Desktop Assistant (Full Control & Voice)

A powerful, full-control AI Desktop Assistant located on **Disk E:** (`E:\AI_Assistant`).
Designed to execute computer control actions, speak and understand **English** and **Urdu (اردو)**, and operate with zero clutter.

---

## 🚀 Quick Run (1-Click)

1. Open folder: `E:\AI_Assistant`
2. Double-click **`run.bat`**
   *(Or run `python main.py` in your terminal)*

---

## 🎙️ Voice Features (English & Urdu)

- **Voice Output (TTS)**:
  - Powered by natural neural speech synthesis with automatic language detection:
    - **English**: `en-US-AriaNeural` (clear natural female) or `en-US-GuyNeural`
    - **Urdu**: `ur-PK-UzmaNeural` (natural Urdu female) or `ur-PK-AsadNeural`
  - Toggle auto-speech on or off anytime using the **🔊 Voice ON/OFF** button in the header bar.
  - Click the **🔊** button on any message to replay it aloud.
- **Voice Input (STT)**:
  - Click the **🎤 Mic** button and speak in English or Urdu. The assistant will transcribe your speech and execute your command.

---

## 💻 Full Computer Control

You can speak or type commands in either **English** or **Urdu / Roman Urdu**. Examples:

### 1. Applications & Windows
- *"Open Chrome"* / *"Chrome kholo"*
- *"Launch Notepad and write Hello World"* / *"Notepad kholo"*
- *"Close Chrome"* / *"Chrome band karo"*
- *"Minimize window"* / *"Show desktop"* / *"Switch window"*

### 2. Audio & Media
- *"Set volume to 75%"* / *"Volume barhao"* / *"Volume 50 percent kardo"*
- *"Mute volume"* / *"Mute kardo"*
- *"Play next song"* / *"Pause music"*

### 3. File Operations
- *"Open downloads folder"* / *"Downloads folder kholo"*
- *"Open Desktop"* / *"E drive kholo"*
- *"Create a file on desktop called notes.txt with text Hello World"*
- *"Create a folder on E drive called ProjectDocs"*
- *"List files in downloads"*
- *"Search for invoice on E drive"*

### 4. System & Hardware
- *"Check system specs"* / *"Drive space kitni bachi hai"* (checks C: and E: free space, RAM, CPU)
- *"Take a screenshot"* / *"Screenshot lo"*
- *"Empty recycle bin"* / *"Recycle bin khali kardo"*
- *"Lock PC"* / *"Lock kardo"*
- *"Sleep PC"* / *"Shutdown in 1 minute"*

### 5. Web & Search
- *"Search YouTube for tutorial"*
- *"Search Google for latest tech news"*
- *"Open github.com"*

### 6. Screen Snipping
- Press **Ctrl + Shift + D** anywhere on Windows to drag and crop any error message, code, or screen region for instant AI diagnosis.

---

## ⚙️ Configuration & API Key

Open `E:\AI_Assistant\.env` and paste your free Google Gemini API key:
```env
GOOGLE_API_KEY=AIzaSy...
```
*(You can also configure API keys, models, and custom voices anytime by clicking the ⚙️ Settings button in the app).*
