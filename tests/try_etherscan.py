import os
import requests
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("ETHERSCAN_API_KEY")

params = {
    "chainid": 1,
    "module": "contract",
    "action": "getsourcecode",
    "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "apikey": key,
}

r = requests.get(
    "https://api.etherscan.io/v2/api",
    params=params,
    timeout=60
)

print("HTTP status:", r.status_code)

data = r.json()

print("status/message:", data.get("status"), data.get("message"))

result = data.get("result", [])

if isinstance(result, list) and result:
    info = result[0]

    for k, v in info.items():
        print(f"{k}: {str(v)[:70]!r}")
else:
    print("result:", result)