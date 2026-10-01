import requests
import json

from config import OLLAMA_URL, MODEL, NUM_CTX, NUM_PREDICT, OLLAMA_READ_TIMEOUT
from errors import OllamaError, OllamaUnavailableError, ModelNotInstalledError


def check_ollama():
    # Fail fast, before spending Etherscan calls, if Ollama or the model is missing.
    try:
        r = requests.get(OLLAMA_URL + "/api/tags", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        raise OllamaUnavailableError(
            "Cannot reach Ollama at %s. Start the Ollama app "
            "(or run 'ollama serve') and try again." % OLLAMA_URL
        )

    try:
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except ValueError:
        raise OllamaError("Ollama returned an unreadable reply to the model-list request.")

    wanted = MODEL if ":" in MODEL else MODEL + ":latest"
    if wanted not in names:
        raise ModelNotInstalledError(
            "Model '%s' is not installed. Run: ollama pull %s" % (MODEL, MODEL)
        )


def analyze(system_prompt, user_prompt):
    # Returns (text, done_reason). done_reason == "length" means the reply was cut off.
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    }

    try:
        r = requests.post(
            OLLAMA_URL + "/api/chat",
            json=payload,
            timeout=(5, OLLAMA_READ_TIMEOUT),
        )
    except requests.Timeout:
        raise OllamaError(
            "The local model took longer than %d s. Try a smaller model, "
            "less max_tokens, or increase OLLAMA_READ_TIMEOUT."
            % OLLAMA_READ_TIMEOUT
        )
    except requests.ConnectionError:
        raise OllamaUnavailableError(
            "Lost connection to Ollama. Is it still running?"
        )

    if r.status_code == 404:
        raise ModelNotInstalledError(
            "Ollama says model '%s' was not found. Run: ollama pull %s"
            % (MODEL, MODEL)
        )

    if r.status_code >= 400:
        hint = (
            "(often means not enough memory: try a smaller model)"
            if r.status_code == 500
            else ""
        )
        raise OllamaError(
            "Ollama returned HTTP %s: %s %s"
            % (r.status_code, hint, r.text[:200])
        )

    try:
        body = r.json()
        text = body["message"]["content"]
    except (ValueError, KeyError, TypeError):
        raise OllamaError("Ollama gave a reply in an unexpected format.")

    if not text or not text.strip():
        raise OllamaError("The model returned an empty answer.")

    return text.strip(), body.get("done_reason")


def analyze_streaming(system_prompt, user_prompt):
    payload = {
        "model": MODEL,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
    }

    chunks = []

    with requests.post(
        OLLAMA_URL + "/api/chat",
        json=payload,
        timeout=(5, OLLAMA_READ_TIMEOUT),
        stream=True,
    ) as r:
        r.raise_for_status()

        for line in r.iter_lines():
            if not line:
                continue

            piece = json.loads(line)
            token = piece.get("message", {}).get("content", "")

            print(token, end="", flush=True)
            chunks.append(token)

            if piece.get("done"):
                return "".join(chunks).strip(), piece.get("done_reason")