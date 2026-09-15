"""Calculate the next stable SemVer release from Git history."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
GIT_BIN = os.environ.get("GIT_BIN") or shutil.which("git") or "git"
SEMVER_RE = re.compile(r"^v(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?:\s+",
    re.IGNORECASE,
)


def _git(*args: str) -> str:
    return subprocess.check_output(
        [GIT_BIN, "-C", str(ROOT_DIR), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def _version_tuple(tag: str) -> tuple[int, int, int] | None:
    match = SEMVER_RE.fullmatch(tag)
    if not match:
        return None
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def latest_stable_tag() -> tuple[str, tuple[int, int, int]]:
    tags = _git("tag", "--list", "v*").splitlines()
    parsed = [(tag, _version_tuple(tag)) for tag in tags]
    stable = [(tag, version) for tag, version in parsed if version is not None]
    if not stable:
        return "v0.0.0", (0, 0, 0)
    return max(stable, key=lambda item: item[1])


def commit_messages(base_tag: str) -> list[str]:
    revision = f"{base_tag}..HEAD"
    output = _git("log", revision, "--format=%s%n%b%x00")
    return [message.strip() for message in output.split("\x00") if message.strip()]


def change_level(messages: list[str]) -> str:
    has_feature = False
    for message in messages:
        first_line = message.splitlines()[0] if message.splitlines() else message
        match = CONVENTIONAL_RE.match(first_line)
        if match and match.group("type").lower() == "feat":
            has_feature = True
        if (match and match.group("breaking")) or re.search(
            r"(?im)^BREAKING(?:[ -]CHANGE)?\s*:",
            message,
        ):
            return "major"
    return "minor" if has_feature else "patch"


def next_version(
    *,
    level: str = "auto",
    base_tag: str = "",
) -> dict[str, object]:
    discovered_tag, current = latest_stable_tag()
    base = base_tag or discovered_tag
    if base_tag:
        parsed_base = _version_tuple(base_tag)
        if parsed_base is None:
            raise ValueError("base tag must be a stable vMAJOR.MINOR.PATCH tag")
        current = parsed_base
    messages = commit_messages(base)
    selected_level = change_level(messages) if level == "auto" else level
    if selected_level not in {"major", "minor", "patch"}:
        raise ValueError("level must be auto, major, minor, or patch")
    major, minor, patch = current
    if selected_level == "major":
        next_tuple = (major + 1, 0, 0)
    elif selected_level == "minor":
        next_tuple = (major, minor + 1, 0)
    else:
        next_tuple = (major, minor, patch + 1)
    return {
        "currentVersion": f"v{major}.{minor}.{patch}",
        "nextVersion": f"v{next_tuple[0]}.{next_tuple[1]}.{next_tuple[2]}",
        "level": selected_level,
        "baseTag": base,
        "commitCount": len(messages),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calculate the next stable vMAJOR.MINOR.PATCH version."
    )
    parser.add_argument(
        "--level",
        choices=("auto", "major", "minor", "patch"),
        default="auto",
        help="release level; auto reads Conventional Commit messages",
    )
    parser.add_argument("--base-tag", default="", help="stable tag to use as the base")
    parser.add_argument("--json", action="store_true", help="print a JSON result")
    args = parser.parse_args()
    result = next_version(level=args.level, base_tag=args.base_tag)
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    else:
        print(result["nextVersion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
