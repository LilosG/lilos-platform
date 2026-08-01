from pathlib import Path

from scripts.check_secrets import find_secret_patterns, validate_env_example


def test_env_example_accepts_names_with_empty_values(tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("FIRST_NAME=\nSECOND_NAME=\n", encoding="utf-8")

    assert validate_env_example(env_example) == []


def test_env_example_rejects_values(tmp_path: Path) -> None:
    env_example = tmp_path / ".env.example"
    env_example.write_text("SECRET_NAME=not-a-real-secret\n", encoding="utf-8")

    assert validate_env_example(env_example) == [".env.example:1: example values must be empty"]


def test_secret_pattern_scan_reports_path_without_value(tmp_path: Path) -> None:
    source = tmp_path / "settings.py"
    token_shape = "ghp_" + ("a" * 36)
    source.write_text(f"TOKEN = '{token_shape}'\n", encoding="utf-8")

    assert find_secret_patterns(tmp_path) == ["settings.py: matched GitHub token pattern"]
