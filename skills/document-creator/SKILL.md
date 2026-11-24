---
name: document-creator
description: Autonomous generation of publication-grade PDF reports, formatted Microsoft Word (.docx) documents, and widescreen PowerPoint (.pptx) pitch presentations.
slash_command: /docs
keywords: pdf, docx, word, presentation, pptx, slides, document, report, export, create_pdf, create_word, create_presentation
---

## Document Creator Directives
- **Direct File Generation**: Never just output raw text when the user asks for a document — execute `[action:create_pdf:filename:content]`, `[action:create_word:filename:content]`, or `[action:create_presentation:filename:content]` so the file is created and opened on Desktop.
- **Executive Typography & Styling**: Use proper hierarchical headings (`# `, `## `, `### `), bullet points, and clean tables.
- **Presentations**: Use `---` delimiters between slides. The first slide is the title slide; following slides contain high-impact titles and punchy bullet takeaways.
- **Zero Friction Delivery**: Save files with clean, descriptive names on the user's Desktop for instant access.
