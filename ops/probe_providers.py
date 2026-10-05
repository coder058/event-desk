"""Read-only model inventory; neither secret values nor error response bodies are printed."""
from pathlib import Path

import httpx

env = {}
for line in (Path.home() / ".eventdesk/.env").read_text(encoding="utf-8-sig").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        name, value = line.split("=", 1)
        env[name.strip()] = value.strip().strip('"').strip("'")
calls = [("gemini", "https://generativelanguage.googleapis.com/v1beta/models",
          {"x-goog-api-key": env["GEMINI_API_KEY"]}),
         ("groq", "https://api.groq.com/openai/v1/models", {"Authorization": "Bearer " + env["GROQ_API_KEY"]})]
for provider, url, headers in calls:
    try:
        response = httpx.get(url, headers=headers, timeout=15)
        print(provider, "http", response.status_code)
        if response.status_code == 200:
            body = response.json()
            models = [item.get("name", item.get("id")) for item in body.get("models", body.get("data", []))]
            print(provider, "candidate_ids", [m for m in models if isinstance(m, str) and ("flash" in m or "gpt-oss" in m)])
            if provider == "groq":
                print(provider, "root_fields", list(body), "model_ids", models)
    except httpx.HTTPError as error:
        print(provider, "error_type", type(error).__name__)
