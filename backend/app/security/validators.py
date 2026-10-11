"""
validators.py
-------------
Custom Pydantic / input validators for security.

Prevents common injection and malformed input.
"""

import re
from typing import Any

from pydantic import validator

def sanitize_string(value: str) -> str:
    """Basic sanitization for user-controlled strings."""
    if not isinstance(value, str):
        return value
    # Remove control characters and limit length
    value = re.sub(r'[\x00-\x1F\x7F]', '', value)
    return value.strip()[:500]

class SecureString(str):
    """Custom type that auto-sanitizes."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> str:
        if not isinstance(v, str):
            raise ValueError("must be a string")
        return sanitize_string(v)
