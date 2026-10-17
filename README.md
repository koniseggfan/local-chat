# Vortex AI

A branded Vortex AI chat app with private accounts, saved conversations, web and Wikipedia research on every question, related Wikimedia Commons image previews, and OpenAI-powered answers.

## Run locally

Install Python 3.11 or later, then run:

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-api-key"
python app.py
```

Open `http://127.0.0.1:5000`. Vortex uses `gpt-6-luna` by default and searches the web and Wikipedia for every question. Relevant Wikimedia Commons pictures appear with their source and license when available. Set `OPENAI_MODEL` to choose another supported model. Without `OPENAI_API_KEY`, Vortex still displays live search snippets, links, and Commons pictures; full AI-generated answers require the key.

## Deploy on Render

The included `render.yaml` defines a free web service and generates a secret session key. Set `OPENAI_API_KEY` as a secret environment variable in Render; never commit the key to this repository. API usage is billed separately by OpenAI. The free Render service uses an ephemeral filesystem, so SQLite accounts and conversations can be lost after a restart or sleep.

