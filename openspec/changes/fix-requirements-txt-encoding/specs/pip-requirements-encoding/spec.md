## ADDED Requirements

### Requirement: requirements.txt is UTF-8 LF

The repository root `requirements.txt` MUST be encoded as UTF-8 without a byte-order mark and MUST use Unix LF (`\n`) line endings only. It MUST NOT be stored as UTF-16 (or any encoding that inserts NUL bytes between ASCII characters).

#### Scenario: File decodes as UTF-8 without NUL padding

- **WHEN** a tool reads `requirements.txt` as UTF-8 bytes
- **THEN** the file MUST decode successfully, MUST contain no `\0` bytes, and MUST NOT require UTF-16 decoding to recover package names

#### Scenario: Line endings are LF-only

- **WHEN** `requirements.txt` is inspected for line endings
- **THEN** the file MUST use LF only and MUST NOT contain carriage-return (`\r`) characters

### Requirement: Dependency content is unchanged by encoding conversion

Converting `requirements.txt` encoding MUST preserve every dependency line exactly (package names, version operators, pins, comments, and blank-line structure aside from newline normalization). Package names and versions MUST NOT be added, removed, or altered.

#### Scenario: Package list identity after conversion

- **WHEN** `requirements.txt` is converted from UTF-16 to UTF-8 LF
- **THEN** the logical dependency lines MUST match the pre-conversion content (same packages and versions)

### Requirement: Linux pip can read requirements.txt

`requirements.txt` MUST be readable by pip on Linux hosts via `pip install -r requirements.txt` (or an equivalent dry-run parse) without encoding or NUL-related parse failures attributable to file encoding.

#### Scenario: Pip parses the requirements file

- **WHEN** pip is invoked with `-r requirements.txt` on a Linux-compatible UTF-8 interpretation of the file
- **THEN** pip MUST successfully parse the file (no UnicodeDecodeError / garbled requirement lines caused by UTF-16 storage)
