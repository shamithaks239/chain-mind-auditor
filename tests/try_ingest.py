from etherscan import fetch_contract
from errors import ChainMindError


for addr in [
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "0x123",
]:
    try:
        info = fetch_contract(addr)

        print(
            "OK:",
            info["ContractName"],
            info["CompilerVersion"],
            len(info["SourceCode"]),
            "chars"
        )

    except ChainMindError as e:
        print("ERR:", type(e).__name__, "-", e)