---
name: creative-studio
description: Autonomous generation of high-resolution AI art, branded QR codes, voice speech playback, and creative digital media.
slash_command: /creative
keywords: image, picture, draw, art, qrcode, qr, voice, speak, tts, photo, wallpaper, logo, design
---

## Creative Studio Directives
- **Direct Art Delivery**: When asked to create, draw, generate, or paint an image or art, emit `[action:generate_image:detailed_visual_prompt]`. The image will be downloaded in high resolution (1024x1024) and saved directly to the user's Desktop.
- **QR Codes**: When asked to generate a QR code for a website, link, WiFi network, or text, emit `[action:create_qrcode:content:optional_filename.png]` to render a high-contrast vector QR code on Desktop.
- **Voice Playback**: When requested to speak or read aloud, emit `[action:speak:text]` using natural neural voices.
- **Descriptive Excellence**: Enhance prompts with lighting, mood, artistic medium, and color palette details for optimal visual fidelity.
