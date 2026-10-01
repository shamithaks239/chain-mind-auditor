import argparse
import secrets
import sys
import time
from pathlib import Path

from config import MODEL
from errors import ChainMindError
from etherscan import fetch_contract
from sanitizer import prepare_source, safe_meta
from ollama_client import check_ollama, analyze
from prompts import SYSTEM_PROMPT, build_user_prompt, missing_sections


DISCLAIMER = (
    "NOTE: This is an automated, LLM-generated analysis intended as assistance. "
    "It is NOT a formal security audit and may contain errors or omissions. "
    "Verify anything important manually."
)


def step(text):
    print(text + "...", end=" ", flush=True)


def done(extra=""):
    print("\u2713" + (f" ({extra})" if extra else ""))


def run(args):
    print("=== Chain-Mind Auditor ===")

    if args.file:
        code = Path(args.file).read_text(
            encoding="utf-8",
            errors="replace"
        )

        info = {
            "SourceCode": code,
            "ContractName": Path(args.file).stem,
            "CompilerVersion": "local file",
            "Address": "local file",
        }

    else:
        address = args.address or input(
            "Enter contract address: "
        ).strip()

    step("Checking Ollama and model")
    check_ollama()
    done(MODEL)

    if not args.file:
        step("Fetching contract from Etherscan")
        info = fetch_contract(address)
        done(safe_meta(info.get("ContractName")))

    step("Sanitizing source code")
    prepared = prepare_source(info)

    done(
        "%d -> %d chars, %d file(s)"
        % (
            prepared.original_chars,
            prepared.final_chars,
            len(prepared.files_included),
        )
    )

    if prepared.injection_hits:
        print("  ! Instruction-like text found inside the contract")
        print("    (possible prompt-injection attempt):")

        for h in prepared.injection_hits:
            print("      -", h)

    if prepared.truncated:
        print(
            "  ! Source was truncated to fit the model's context; "
            "the analysis is PARTIAL."
        )

    boundary = secrets.token_hex(6)

    prompt = build_user_prompt(
        info,
        prepared,
        boundary
    )

    step(
        "Sending contract to local LLM "
        "(this can take several minutes on a laptop CPU)"
    )

    t0 = time.time()

    text, reason = analyze(
        SYSTEM_PROMPT,
        prompt
    )

    done(
        "%.0fs" % (time.time() - t0)
    )

    print("\n" + "=" * 72)

    print(
        "CONTRACT: %s    ADDRESS: %s"
        % (
            safe_meta(info.get("ContractName")),
            info.get("Address", "n/a"),
        )
    )

    print(
        "MODEL: %s (running locally via Ollama)"
        % MODEL
    )

    print("=" * 72 + "\n")

    print(text)

    missing = missing_sections(text)

    if missing:
        print(
            "\n  ! The model omitted these expected sections: "
            + ", ".join(missing)
        )

    if reason == "length":
        print(
            "\n  ! The reply hit the length limit and may be cut off "
            "(raise NUM_PREDICT)."
        )

    print("\n" + "-" * 72 + "\n" + DISCLAIMER)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Chain-Mind Auditor"
    )

    parser.add_argument(
        "address",
        nargs="?",
        help="contract address (0x...)"
    )

    parser.add_argument(
        "--file",
        help="analyze a local .sol file instead of fetching from Etherscan"
    )

    args = parser.parse_args()

    try:
        run(args)
        return 0

    except ChainMindError as exc:
        print("\u2717\n\nError: %s" % exc)
        return 1

    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130

    except Exception as exc:
        # last-resort net: never show a raw traceback
        print(
            "\u2717\n\nUnexpected error (%s): %s"
            % (type(exc).__name__, exc)
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())