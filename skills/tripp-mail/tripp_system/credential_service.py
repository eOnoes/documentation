import argon2

class CredentialService:
    """Argon2 credential hashing for API keys and passwords.

    Uses argon2-cffi with the default ``Argon2id`` variant, memory-hard
    parameters tuned to ~100 ms verification on production hardware, and
    automatic re-hash detection when parameters change.
    """

    _PH = argon2.PasswordHasher(
        time_cost=3,       # iterations
        memory_cost=65536, # 64 MiB
        parallelism=4,     # threads
        hash_len=32,       # output length in bytes
        salt_len=16,       # random salt length in bytes
    )

    @classmethod
    def hash(cls, secret: str) -> str:
        """Hash a password or API key and return the encoded string."""
        return cls._PH.hash(secret)

    @classmethod
    def verify(cls, secret: str, encoded: str) -> bool:
        """Verify *secret* against an Argon2 hash string."""
        try:
            return cls._PH.verify(encoded, secret)
        except (argon2.exceptions.VerificationError,
                argon2.exceptions.InvalidHashError):
            return False

    @classmethod
    def rehash(cls, secret: str, encoded: str) -> tuple[bool, str | None]:
        """Check whether *encoded* needs re-hashing due to parameter changes."""
        try:
            if cls._PH.check_needs_rehash(encoded):
                return True, cls._PH.hash(secret)
            return False, None
        except (argon2.exceptions.VerificationError,
                argon2.exceptions.InvalidHashError):
            return True, None

