import os
from dotenv import load_dotenv

load_dotenv()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = int(os.getenv("CHAIN_ID", "1"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "")

NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
NUM_PREDICT = int(os.getenv("NUM_PREDICT", "1200"))
OLLAMA_READ_TIMEOUT = int(os.getenv("OLLAMA_READ_TIMEOUT", "600"))

MAX_CODE_CHARS = int(os.getenv("MAX_CODE_CHARS", "16000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))