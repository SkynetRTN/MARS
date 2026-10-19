"""Shared passband token candidates (CAT-01 explicit case distinction)."""


def filter_token_candidates(image_filter: str) -> list[str]:
    """Keep Johnson V and SkyMapper v distinct; retain other legacy variants."""
    tokens = [image_filter, image_filter.strip()]
    if image_filter.strip() not in {"V", "v"}:
        tokens.extend((image_filter.lower(), image_filter.upper()))
    tokens.append(image_filter.replace("′", "'").replace("’", "'"))
    return list(dict.fromkeys(tokens))
