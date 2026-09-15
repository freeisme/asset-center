"""Compatibility entry point for the tracked migration runner."""

from tools.migration_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
