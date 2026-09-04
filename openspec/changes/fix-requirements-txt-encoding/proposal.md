## Why

`requirements.txt` is stored as UTF-16 (Windows-style wide encoding). Linux `pip install -r requirements.txt` expects UTF-8 (or plain ASCII) with LF line endings, so install/deploy steps fail or mis-parse dependency lines when the file is read as UTF-8.

## What Changes

- Convert `requirements.txt` from UTF-16 to UTF-8 without BOM, with LF line endings.
- Keep every package name and version pin exactly unchanged—encoding and newlines only.
- Verify the file is readable by Linux-style `pip` (decode as UTF-8; no NUL/`\r` artifacts from UTF-16).

## Capabilities

### New Capabilities

- `pip-requirements-encoding`: The project dependency lock file `requirements.txt` MUST be UTF-8 (no BOM) with LF line endings so Linux pip and CI/deploy hosts can install dependencies reliably.

### Modified Capabilities

- (none)

## Impact

- **Files:** `requirements.txt` only (byte encoding / line endings)
- **Systems:** Local/CI `pip install -r`, production deploy dependency install
- **APIs / Django / package versions:** None—dependency list content unchanged
- **Risk:** Low; pure encoding fix
