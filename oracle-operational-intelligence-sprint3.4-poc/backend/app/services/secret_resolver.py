import os

class SecretResolutionError(RuntimeError):
    pass

def resolve_secret(reference: str) -> str:
    """Resolve a secret without persisting clear text in the platform DB.

    Phase 2 supports env://NAME for local/dev usage. Production providers
    (AWS Secrets Manager, Vault, etc.) plug into this same interface later.
    """
    if reference.startswith("env://"):
        key = reference.removeprefix("env://")
        value = os.getenv(key)
        if not value:
            raise SecretResolutionError(f"Environment secret {key!r} is not set")
        return value
    raise SecretResolutionError("Unsupported secret reference. Phase 2 supports env://NAME")
