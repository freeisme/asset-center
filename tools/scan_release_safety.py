"""Release safety scan.

Fails when a revision still contains credentials, internal network details,
local machine paths or business identifiers that must never be published.
Run it before every push or release::

    python tools/scan_release_safety.py --rev HEAD

The scan reads files from the git object store, so it also works in CI on a
fresh checkout. Exit code 1 means at least one finding; the report lists the
file, line and matched rule.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SELF_PATH = "tools/scan_release_safety.py"

TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".service",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

FORBIDDEN_FILES = (
    re.compile(r"(^|/)\.env$"),
    re.compile(r"\.sql\.gz$"),
    re.compile(r"\.bundle$"),
    re.compile(r"\.xlsx?$"),
    re.compile(r"\.log$"),
    re.compile(r"(^|/)PROJECT_HANDOVER\.md$"),
)

# Rules are ordered from most dangerous to least. Add new production
# identifiers here, never inside documents or test fixtures.
RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "cloud-or-personal-access-token",
        re.compile(
            r"(ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
            r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9]{20,})"
        ),
    ),
    ("private-key-material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("ssh-key-material", re.compile(r"(ssh-rsa|ssh-ed25519|ecdsa-sha2-nistp256) AAAA")),
    (
        "internal-ipv4",
        re.compile(
            r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"
        ),
    ),
    (
        "local-machine-path",
        re.compile(r"\b[CDEF]:\\\\(?:Users|数据库|work|项目|temp|Temp)\b"),
    ),
    (
        "local-mysql-path",
        re.compile(r"[A-Za-z]:\\\\?MySQL|MySQL\\\\bin"),
    ),
    (
        "hardcoded-credential",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key)\b\s*[:=]\s*"
            r"[\"'][^\"'<>{}$\s]{6,}[\"']"
        ),
    ),
    (
        "business-employee-number",
        re.compile(r"\b[A-Z]{2,6}-[A-Z]{2,6}-[A-Z]{1,4}-\d{3}\b"),
    ),
    (
        "internal-account-name",
        re.compile(r"\badmin1\b|gitea-office-asset|server-admin"),
    ),
)

PLACEHOLDER_HINTS = (
    "replace-with",
    "change-me",
    "example",
    "placeholder",
    "your-",
    "xxx",
    "***",
    "替换",
    "安全配置",
    "读取",
    "占位",
    "示例",
    "<",
    "...",
)

# Hostname-style matches are checked separately so container/DNS helper names
# and reserved documentation domains are allowed while real internal names are
# still reported by the `internal-hostname` rule.
INTERNAL_HOST_PATTERN = re.compile(
    r"\b([A-Za-z0-9][A-Za-z0-9.-]*\.(?:local|lan|internal))\b"
)
ALLOWED_INTERNAL_HOST_SUFFIXES = (
    ".docker.internal",
    ".example.internal",
)


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT_DIR), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout


def tracked_files(revision: str) -> list[str]:
    output = git("ls-tree", "-r", "--name-only", revision)
    return [line.strip() for line in output.splitlines() if line.strip()]


def file_content(revision: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(ROOT_DIR), "show", f"{revision}:{path}"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


def scan(revision: str) -> list[str]:
    findings: list[str] = []
    for path in tracked_files(revision):
        if path == SELF_PATH:
            # The scanner contains the rule patterns themselves.
            continue
        for pattern in FORBIDDEN_FILES:
            if pattern.search(path):
                findings.append(f"{path}: forbidden file for a public release")
        if Path(path).suffix.lower() not in TEXT_EXTENSIONS and "." in Path(path).name:
            continue
        content = file_content(revision, path)
        if content is None:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if not line.strip():
                continue
            for rule_name, regex in RULES:
                match = regex.search(line)
                if not match:
                    continue
                if rule_name == "hardcoded-credential" and is_placeholder(match.group(0)):
                    continue
                excerpt = match.group(0)[:60]
                findings.append(f"{path}:{line_number}: {rule_name} -> {excerpt}")
            for host_match in INTERNAL_HOST_PATTERN.finditer(line):
                host = host_match.group(1).lower()
                if host.endswith(ALLOWED_INTERNAL_HOST_SUFFIXES):
                    continue
                findings.append(
                    f"{path}:{line_number}: internal-hostname -> {host[:60]}"
                )
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a revision for sensitive content.")
    parser.add_argument("--rev", default="HEAD", help="Revision to scan (default: HEAD)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        findings = scan(args.rev)
    except RuntimeError as error:
        print(f"Release safety scan failed: {error}", file=sys.stderr)
        return 2
    if findings:
        print(f"Release safety scan found {len(findings)} issue(s):")
        for item in findings:
            print(f"  {item}")
        print("Remove or replace the content above before pushing or releasing.")
        return 1
    print(f"Release safety scan passed for {args.rev}: no sensitive content detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
