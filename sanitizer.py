import json
import re
import unicodedata
from dataclasses import dataclass, field

from config import MAX_CODE_CHARS
from errors import SanitizationError


def extract_sources(info):
    # Return {file_path: code} from Etherscan's SourceCode field.
    raw = (info.get("SourceCode") or "").strip()

    if not raw:
        raise SanitizationError("The source code field is empty.")

    name = info.get("ContractName") or "Contract"

    if raw.startswith("{{") and raw.endswith("}}"):
        raw = raw[1:-1]                 # shape 2: wrapped JSON

    if raw.startswith("{"):             # shapes 2 and 3
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise SanitizationError(
                "Could not parse the multi-file source JSON."
            )

        if not isinstance(parsed, dict):
            raise SanitizationError(
                "Unexpected structure in the source JSON."
            )

        files = (
            parsed.get("sources")
            if isinstance(parsed.get("sources"), dict)
            else parsed
        )

        out = {}

        for path, entry in files.items():
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("content"), str)
            ):
                out[str(path)] = entry["content"]

        if not out:
            raise SanitizationError(
                "No Solidity files were found inside the source JSON."
            )

        return out

    return {name + ".sol": raw}          # shape 1: single file
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HIDDEN_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts|rules)",
    r"disregard (all |any )?(the )?(previous|prior|above) (instructions|prompts|rules)",
    r"you are now",
    r"system prompt",
    r"(do not|don't) (report|flag|mention)",
    r"report (rate|mark|describe) (this|the) contract as (safe|secure|audited)",
    r"</?\s*system",
]

INJECTION_RE = re.compile(
    "|".join(INJECTION_PATTERNS),
    re.IGNORECASE
)
def clean_text(text):
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = CONTROL_RE.sub("", text)
    return HIDDEN_RE.sub("", text)

def find_injection_phrases(files):
    hits = []

    for path, code in files.items():
        for m in INJECTION_RE.finditer(code):
            hits.append(
                "%s: %r" % (path, m.group(0)[:60])
            )

    return hits[:5]
def safe_meta(value, max_len=60):
    value = re.sub(r"[^A-Za-z0-9_.-]", " ", str(value or "unknown"))
    return value[:max_len] or "unknown"
def safe_path(path):
    return re.sub(
        r"[^A-Za-z0-9_./-]",
        "",
        str(path)
    )[:120] or "file.sol"
def strip_comments(code):
    out, i, n = [], 0, len(code)

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if c in ('"', "'"):
            q = c
            j = i + 1

            while j < n and code[j] != q:
                j += 2 if code[j] == "\\" else 1

            out.append(code[i:j + 1])
            i = j + 1

        elif c == "/" and nxt == "/":
            j = code.find("\n", i)

            if j == -1:
                break

            i = j

        elif c == "/" and nxt == "*":
            j = code.find("*/", i + 2)

            if j == -1:
                i = n
            else:
                i = j + 2

        else:
            out.append(c)
            i += 1

    text = "".join(out)
    text = re.sub(r"[ \t]+\n", "\n", text)

    return re.sub(r"\n\s*\n+", "\n", text).strip()
LIB_HINTS = (
    "openzeppelin",
    "node_modules",
    "@chainlink",
    "solmate",
    "forge-std",
    "hardhat/console"
)
@dataclass
class PreparedSource:
    text: str
    files_included: list = field(default_factory=list)
    libraries_skipped: list = field(default_factory=list)
    omitted: list = field(default_factory=list)
    truncated: bool = False
    injection_hits: list = field(default_factory=list)
    original_chars: int = 0
    final_chars: int = 0

def prepare_source(info, max_chars=MAX_CODE_CHARS):
    files = extract_sources(info)

    hits = find_injection_phrases(files)

    cleaned = {
        p: strip_comments(clean_text(c))
        for p, c in files.items()
    }

    cleaned = {
        p: c
        for p, c in cleaned.items()
        if c.strip()
    }

    if not cleaned:
        raise SanitizationError(
            "After cleaning, no source code remained."
        )

    libs = [
        p for p in cleaned
        if any(h in p.lower() for h in LIB_HINTS)
    ]

    project = {
        p: c for p, c in cleaned.items()
        if p not in libs
    }

    if not project:
        project = cleaned
        libs = []

    name = safe_meta(info.get("ContractName") or "")

    ordered = sorted(
        project.keys(),
        key=lambda kv: (
            ("contract " + name).lower() not in kv.lower(),
            kv.lower()
        )
    )

    parts, used, included, omitted, truncated = [], 0, [], [], False

    for idx, path in enumerate(ordered):
        code = project[path]

        block = (
            "===== FILE: %s =====\n%s\n"
            % (safe_path(path), code)
        )

        room = max_chars - used

        if len(block) <= room:
            parts.append(block)
            used += len(block)
            included.append(path)

        else:
            if room > 500:
                parts.append(block[:room])
                used += room
                included.append(path)
                truncated = True
            else:
                omitted.append(path)

            omitted.extend(ordered[idx + 1:])
            truncated = True
            break

    text = "\n".join(parts)

    return PreparedSource(
        text=text,
        files_included=included,
        libraries_skipped=libs,
        omitted=omitted,
        truncated=truncated,
        injection_hits=hits,
        original_chars=sum(len(c) for c in files.values()),
        final_chars=len(text),
    )
