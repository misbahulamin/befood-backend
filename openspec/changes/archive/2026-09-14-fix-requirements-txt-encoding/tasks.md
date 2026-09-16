## 1. Convert encoding

- [x] 1.1 Decode `requirements.txt` as UTF-16 and capture the exact logical dependency lines
- [x] 1.2 Rewrite `requirements.txt` as UTF-8 without BOM with LF line endings only
- [x] 1.3 Confirm package names and versions match the pre-conversion content (no adds/removes/edits)

## 2. Verify for Linux pip

- [x] 2.1 Confirm the file has zero `\0` bytes and zero `\r` bytes and decodes as UTF-8
- [x] 2.2 Run a pip dry-run or parse check with `-r requirements.txt` to confirm Linux-pip readability
