"""Pinned standard text-only pricing; verified 2026-10-28, recheck before activation."""

MODEL = "gpt-5.4-mini-2026-03-17"
PRICE_VERSION = "2026-10-28-standard"
MAX_INPUT_TOKENS = 400_000
MAX_OUTPUT_TOKENS = 1600


def micro_usd(input_tokens: int, output_tokens: int) -> int:
    if (
        type(input_tokens) is not int
        or type(output_tokens) is not int
        or not 0 <= input_tokens <= MAX_INPUT_TOKENS
        or not 0 <= output_tokens <= MAX_OUTPUT_TOKENS
    ):
        raise ValueError("Untrusted token usage")
    # $0.75/$4.50 per million; ceil each response, no cache discount assumption.
    return (input_tokens * 3 + output_tokens * 18 + 3) // 4


# Reserve the model's entire context input ceiling, not an estimated byte/token ratio.
MAX_REQUEST_MICRO_USD = micro_usd(MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS)
