"""Encode quiz questions for embedding in notebooks."""

import base64


def to_base64(payload: str) -> str:
    """
    Base64-encode a string payload.

    Parameters
    ----------
    payload : str
        JSON string to encode.

    Returns
    -------
    str
        Base64-encoded string.
    """
    return base64.b64encode(bytes(payload, "utf8")).decode()
