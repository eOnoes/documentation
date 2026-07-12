"""Round 21 identity tests for Argon2 credentials and UUIDv4 message IDs."""
from pathlib import Path
import re
import sqlite3
import tempfile
import unittest

PLAN = Path(__file__).with_name("REDESIGN_PLAN.md")
TEXT = PLAN.read_text(encoding="utf-8")


def code_block(section_start, section_end, language):
    section = TEXT.split(section_start, 1)[1].split(section_end, 1)[0]
    return re.search(rf"```{language}\s*\n(.*?)\n```", section, re.S).group(1)


SCHEMA = code_block("## DATABASE SCHEMA v8.4", "## PRODUCTION CODE v8.4", "sql")


def load_production_namespace():
    section = TEXT.split("## PRODUCTION CODE v8.4", 1)[1].split(
        "## SELF-CONTAINED ADVERSARIAL TESTS v8.4", 1
    )[0]
    ns = {"__name__": "round21_embedded_production"}
    for block in re.findall(r"```python\s*\n(.*?)\n```", section, re.S):
        exec(compile(block, str(PLAN), "exec"), ns)
    return ns


PROD = load_production_namespace()


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if mode.lower() != "wal":
        raise AssertionError(mode)
    return db


def insert_message(db, mid, recipient="echo", body="payload"):
    content_hash = __import__("hashlib").sha256(body.encode()).hexdigest()
    db.execute(
        "INSERT INTO messages(id,type,sender,recipient,body,content_hash) VALUES(?,?,?,?,?,?)",
        (mid, "message", "eddie", recipient, body, content_hash),
    )


class CredentialServiceTests(unittest.TestCase):
    """Adversarial tests for Argon2 credential hashing (Round 21)."""

    def test_hash_starts_with_argon2id(self):
        encoded = PROD["CredentialService"].hash("secret")
        self.assertTrue(encoded.startswith("$argon2id$"))

    def test_verify_correct_secret(self):
        encoded = PROD["CredentialService"].hash("correct")
        self.assertTrue(PROD["CredentialService"].verify("correct", encoded))

    def test_verify_wrong_secret(self):
        encoded = PROD["CredentialService"].hash("secret")
        self.assertFalse(PROD["CredentialService"].verify("wrong", encoded))

    def test_verify_empty_string(self):
        encoded = PROD["CredentialService"].hash("secret")
        self.assertFalse(PROD["CredentialService"].verify("", encoded))

    def test_verify_completely_empty_hash(self):
        self.assertFalse(PROD["CredentialService"].verify("secret", ""))

    def test_verify_malformed_hash(self):
        self.assertFalse(PROD["CredentialService"].verify("secret", "not-a-hash"))

    def test_truncated_argon2_returns_false(self):
        self.assertFalse(PROD["CredentialService"].verify("secret", "$argon2id$v=19$"))

    def test_rehash_not_needed(self):
        encoded = PROD["CredentialService"].hash("secret")
        needs, new_hash = PROD["CredentialService"].rehash("secret", encoded)
        self.assertFalse(needs)
        self.assertIsNone(new_hash)

    def test_hash_same_secret_different_results(self):
        h1 = PROD["CredentialService"].hash("same")
        h2 = PROD["CredentialService"].hash("same")
        self.assertNotEqual(h1, h2)

    def test_hash_empty_string(self):
        encoded = PROD["CredentialService"].hash("")
        self.assertTrue(PROD["CredentialService"].verify("", encoded))


class UUIDv4ValidationTests(unittest.TestCase):
    """Adversarial tests for UUIDv4 generation and validation (Round 21)."""

    def test_valid_uuid4_accepted(self):
        mid = PROD["generate_message_id"]()
        self.assertEqual(len(mid), 32)
        self.assertTrue(PROD["validate_message_id"](mid))

    def test_rejection_wrong_length(self):
        self.assertFalse(PROD["validate_message_id"]("abc123"))

    def test_rejection_too_long(self):
        self.assertFalse(PROD["validate_message_id"]("a" * 33))

    def test_rejection_non_hex(self):
        mid = "g" * 32
        self.assertFalse(PROD["validate_message_id"](mid))

    def test_rejection_empty(self):
        self.assertFalse(PROD["validate_message_id"](""))

    def test_rejection_uuidv1(self):
        # UUIDv1 has version nibble = 1, not 4
        mid = "10000000000040008000000000000000"  # version nibble = 1
        self.assertFalse(PROD["validate_message_id"](mid))

    def test_rejection_uuidv3(self):
        # UUIDv3 has version nibble = 3
        mid = "30000000000040008000000000000000"  # version nibble = 3
        self.assertFalse(PROD["validate_message_id"](mid))

    def test_rejection_no_variant_bits(self):
        # Valid version 4 but wrong variant bits (0b00 instead of 0b10)
        mid = "00000000000040000000000000000000"  # variant = 0b00
        self.assertFalse(PROD["validate_message_id"](mid))

    def test_generation_multiple_unique(self):
        ids = {PROD["generate_message_id"]() for _ in range(100)}
        self.assertEqual(len(ids), 100)

    def test_generation_lowercase_hex(self):
        mid = PROD["generate_message_id"]()
        self.assertEqual(mid, mid.lower())

    def test_rejection_uppercase_hex(self):
        mid = PROD["generate_message_id"]().upper()
        self.assertFalse(PROD["validate_message_id"](mid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
