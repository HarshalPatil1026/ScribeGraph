"""Keep secrets out of tool output (which is sent to the LLM and may be traced)."""


def redact(text: str, *secrets: str) -> str:
    """Replace each non-empty secret in ``text`` with ``***``."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text
