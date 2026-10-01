import requests

r = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5-coder:3b",
        "prompt": "In one sentence, what is a Solidity modifier?",
        "stream": False
    },
    timeout=(5, 600),       # connect timeout, read timeout in seconds
)

print(r.status_code)
print(r.json()["response"])