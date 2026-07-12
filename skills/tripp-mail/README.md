# TRIPP.SYSTEM v8.5

Production package extracted from `REDESIGN_PLAN.md`, including the SQLite schema, worker and lease-reaper flow, hash-chained auditing, Argon2 credentials, and UUIDv4 message identities.

## Install

```powershell
python -m pip install -e ".[test]"
```

## Initialize a database

```powershell
python scripts/init_db.py D:\data\tripp.db
```

Use a native absolute path. The parent directory is created when needed.

## Run the tests

```powershell
python -m pytest -q
```

The suite contains 35 Round 19 adversarial tests, 11 Round 20 production tests, and 22 Round 21 identity tests.
