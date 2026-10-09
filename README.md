# Vortex AI

A Flask chat app with user accounts, saved conversations, optional web search, and OpenAI-powered answers.

## Run locally

Install Python 3.11 or later, then run:

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-api-key"
python app.py
```

Open `http://127.0.0.1:5000`. The app uses `gpt-6-luna` by default. Set `OPENAI_MODEL` to choose another supported model. Without `OPENAI_API_KEY`, full AI replies are disabled.

## Deploy on Render

The included `render.yaml` defines a free web service and generates a secret session key. Set `OPENAI_API_KEY` as a secret environment variable in Render; never commit the key to this repository. API usage is billed separately by OpenAI. The free Render service uses an ephemeral filesystem, so SQLite accounts and conversations can be lost after a restart or sleep.
