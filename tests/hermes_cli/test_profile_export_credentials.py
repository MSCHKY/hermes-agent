"""Tests for credential exclusion during profile export.

Profile exports should NEVER include auth.json or .env — these contain
API keys, OAuth tokens, and credential pool data. Users share exported
profiles; leaking credentials in the archive is a security issue.
"""

import tarfile

from hermes_cli.profiles import export_profile, _DEFAULT_EXPORT_EXCLUDE_ROOT


class TestCredentialExclusion:

    def test_auth_json_in_default_exclude_set(self):
        """auth.json must be in the default export exclusion set."""
        assert "auth.json" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_dotenv_in_default_exclude_set(self):
        """.env must be in the default export exclusion set."""
        assert ".env" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_named_profile_export_excludes_auth(self, tmp_path, monkeypatch):
        """Named profile export must not contain auth.json or .env."""
        profiles_root = tmp_path / "profiles"
        profile_dir = profiles_root / "testprofile"
        profile_dir.mkdir(parents=True)

        # Create a profile with credentials plus runtime/history artifacts.
        (profile_dir / "config.yaml").write_text("model: gpt-4\n")
        (profile_dir / "auth.json").write_text('{"tokens": {"access": "redacted"}}')
        (profile_dir / ".env").write_text("OPENROUTER_API_KEY=***\n")
        (profile_dir / "SOUL.md").write_text("I am helpful.\n")
        (profile_dir / "memories").mkdir()
        (profile_dir / "memories" / "MEMORY.md").write_text("# Memories\n")
        for file_name in (
            "state.db",
            "state.db-wal",
            "state.db-shm",
            "gateway_state.json",
            "processes.json",
        ):
            (profile_dir / file_name).write_text("runtime")
        for dir_name in (
            "sessions",
            "backup",
            "backups",
            "state-snapshots",
            "checkpoints",
        ):
            artifact_dir = profile_dir / dir_name
            artifact_dir.mkdir()
            (artifact_dir / "artifact.txt").write_text("runtime")
        (profile_dir / "workspace").mkdir()
        (profile_dir / "workspace" / "request_dump_abc_20260628.json").write_text(
            "runtime"
        )

        monkeypatch.setattr("hermes_cli.profiles._get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("hermes_cli.profiles.validate_profile_name", lambda n: None)

        output = tmp_path / "export.tar.gz"
        result = export_profile("testprofile", str(output))

        # Check archive contents
        with tarfile.open(result, "r:gz") as tf:
            names = tf.getnames()

        assert any("config.yaml" in n for n in names), "config.yaml should be in export"
        assert any("SOUL.md" in n for n in names), "SOUL.md should be in export"
        assert not any("auth.json" in n for n in names), "auth.json must NOT be in export"
        assert not any(".env" in n for n in names), ".env must NOT be in export"
        excluded_names = (
            "state.db",
            "state.db-wal",
            "state.db-shm",
            "gateway_state.json",
            "processes.json",
            "sessions/",
            "backup/",
            "backups/",
            "state-snapshots/",
            "checkpoints/",
            "request_dump_abc_20260628.json",
        )
        for excluded in excluded_names:
            assert not any(excluded in n for n in names), (
                f"{excluded} must NOT be in export"
            )
