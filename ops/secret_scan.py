"""Scan tracked/public source and optionally compare private owner secrets without printing values."""
import argparse
import re
import subprocess
from pathlib import Path


def scan(root: Path, secret_file: Path | None) -> list[str]:
    raw_files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root)
    files = [root / name for name in raw_files.decode().splitlines()]
    owner_values: list[bytes] = []
    if secret_file:
        for line in secret_file.read_bytes().splitlines():
            if b"=" in line and not line.lstrip().startswith(b"#"):
                value = line.split(b"=", 1)[1].strip().strip(b"\"'")
                if value:
                    owner_values.append(value)
    # SOURCE: documented provider token prefixes; exact owner-value comparison supplements pattern checks.
    patterns = [rb"AIza[0-9A-Za-z_-]{30,}", rb"gsk_[0-9A-Za-z]{20,}",
                rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"]
    findings = []
    for path in files:
        if not path.is_file():
            continue
        content = path.read_bytes()
        if any(value in content for value in owner_values) or any(re.search(pattern, content) for pattern in patterns):
            findings.append(str(path.relative_to(root)))
        if path.name == ".env" or path.suffix == ".pem":
            findings.append(str(path.relative_to(root)))
    return sorted(set(findings))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-secrets", type=Path)
    args = parser.parse_args()
    findings = scan(Path.cwd(), args.owner_secrets)
    if findings:
        print("Secret scan failed; affected paths only:", ", ".join(findings))
        raise SystemExit(1)
    print("Secret scan passed; values not emitted")
