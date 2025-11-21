"""
Idempotency Key Generator
Generates unique idempotency keys for Vaulta API requests
"""
import uuid


def generate_idempotency_key() -> str:
    """
    Generate a unique idempotency key for API requests
    
    Returns:
        UUID string in format: 5d20bb83-3b36-4e4f-8c2f-3a8f2b1f8f4a
    """
    return str(uuid.uuid4())
