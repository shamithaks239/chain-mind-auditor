import random
import re
import time
import requests

from config import ETHERSCAN_API_KEY, ETHERSCAN_URL, CHAIN_ID, MAX_RETRIES
from errors import (
    InvalidAddressError,
    EtherscanError,
    EtherscanRateLimitError,
    NotVerifiedError
)


ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def validate_address(address):
    address = (address or "").strip()

    if not ADDRESS_RE.match(address):
        raise InvalidAddressError(
            "That is not a valid Ethereum address. Expected 0x followed by 40 hex characters."
        )

    return address.lower()
def _classify(data):
    # Returns None if fine, "rate_limit" if we should retry,
    # else an error message.
    if not isinstance(data, dict):
        return "Unexpected response shape from Etherscan."

    if str(data.get("status")) == "0":
        result = data.get("result")
        text = ((result if isinstance(result, str) else "") + " " +
                str(data.get("message", ""))).lower()

        if "rate limit" in text:
            return "rate_limit"

        return "Etherscan API error: " + (
            str(result) or str(data.get("message"))
        )

    return None


def _request_with_retries(params):
    if not ETHERSCAN_API_KEY:
        raise EtherscanError(
            "No Etherscan API key found. Add ETHERSCAN_API_KEY to your .env file."
        )

    full = {
        **params,
        "chainid": CHAIN_ID,
        "apikey": ETHERSCAN_API_KEY
    }

    delay = 1.0
    problem = "unknown problem"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                ETHERSCAN_URL,
                params=full,
                timeout=15
            )

            if resp.status_code == 429 or resp.status_code >= 500:
                problem = f"HTTP {resp.status_code}"

            elif resp.status_code >= 400:
                raise EtherscanError(
                    "Etherscan returned HTTP %d." % resp.status_code
                )

            else:
                data = resp.json()
                verdict = _classify(data)

                if verdict == "rate_limit":
                    problem = "rate limit reached"

                elif verdict:
                    raise EtherscanError(verdict)

                else:
                    return data

        except (requests.Timeout, requests.ConnectionError) as exc:
            problem = "network problem (%s)" % type(exc).__name__

        except ValueError:
            raise EtherscanError(
                "Etherscan sent a reply that is not valid JSON."
            )

        if attempt < MAX_RETRIES:
            wait = delay + random.uniform(0, 0.5)

            print(
                "\nRetry %d/%d in %.1fs (attempt %d/%d): %s"
                % (attempt, MAX_RETRIES, wait, attempt, MAX_RETRIES, problem)
            )

            time.sleep(wait)
            delay *= 2

    raise EtherscanRateLimitError(
        "Gave up after %d attempts: %s"
        % (MAX_RETRIES, problem)
    )
def has_code(address):
    data = _request_with_retries({
        "module": "proxy",
        "action": "eth_getCode",
        "address": address,
        "tag": "latest"
    })

    return str(data.get("result", "0x")) not in ("0x", "0x0", "")

def fetch_contract(address):
    address = validate_address(address)

    data = _request_with_retries({
        "module": "contract",
        "action": "getsourcecode",
        "address": address
    })

    result = data.get("result")

    if (
        not isinstance(result, list)
        or not result
        or not isinstance(result[0], dict)
    ):
        raise EtherscanError(
            "Etherscan returned an unexpected result format."
        )

    info = result[0]

    source = info.get("SourceCode") or ""
    abi = info.get("ABI") or ""

    if not source.strip() or abi == "Contract source code not verified":
        if has_code(address):
            raise NotVerifiedError(
                "This contract has code but its source code is not verified "
                "on Etherscan, so there is nothing readable to analyze."
            )

        raise NotVerifiedError(
            "This address is not a contract (it is probably an ordinary wallet)."
        )

    info["Address"] = address

    return info