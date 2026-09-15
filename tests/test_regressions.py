import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


server = load_module("office_asset_server_tests", ROOT / "server.py")
deploy_webhook = load_module(
    "office_asset_deploy_webhook_tests",
    ROOT / "deploy" / "gitea" / "deploy_webhook.py",
)
migration_runner = load_module(
    "office_asset_migration_runner_tests",
    ROOT / "tools" / "migration_runner.py",
)
next_version = load_module(
    "office_asset_next_version_tests",
    ROOT / "tools" / "next_version.py",
)


def empty_snapshot(revision: int = 1) -> dict:
    return {
        "stateRevision": revision,
        **{key: [] for key in server.STATE_ARRAY_KEYS},
    }


class StateValidationTests(TestCase):
    def test_state_snapshot_requires_all_arrays_and_positive_revision(self):
        with self.assertRaises(server.ApiError):
            server.validate_state_payload({})

        invalid_revision = empty_snapshot(0)
        with self.assertRaises(server.ApiError):
            server.validate_state_payload(invalid_revision)

        server.validate_state_payload(empty_snapshot())

    def test_generated_sync_sql_does_not_select_a_fixed_database(self):
        with mock.patch.object(server, "remap_existing_inventory_ids"):
            sql = server.build_sync_sql(empty_snapshot())

        self.assertNotIn("USE office_asset_mgmt", sql.upper())
        self.assertIn("START TRANSACTION;", sql)
        self.assertIn("INSERT INTO app_state_revision", sql)


class AuthenticationHardeningTests(TestCase):
    def test_password_length_limit_is_enforced_before_hashing(self):
        with self.assertRaises(server.ApiError):
            server.password_hash("x" * (server.PASSWORD_MAX_LENGTH + 1))

        self.assertFalse(
            server.verify_password("x" * (server.PASSWORD_MAX_LENGTH + 1), "not-a-hash")
        )

    def test_login_rate_limit_applies_to_ip_and_username(self):
        handler = SimpleNamespace(client_address=("198.51.100.10", 4321))
        original_limit = server.LOGIN_RATE_MAX_ATTEMPTS
        server.LOGIN_RATE_BUCKETS.clear()
        server.LOGIN_RATE_MAX_ATTEMPTS = 2
        try:
            server.enforce_login_rate_limit(handler, "qa_admin")
            server.enforce_login_rate_limit(handler, "qa_admin")
            with self.assertRaises(server.RateLimitError) as context:
                server.enforce_login_rate_limit(handler, "qa_admin")
            self.assertGreaterEqual(context.exception.retry_after, 1)
        finally:
            server.LOGIN_RATE_MAX_ATTEMPTS = original_limit
            server.LOGIN_RATE_BUCKETS.clear()

    def test_secure_cookie_clear_headers_match_secure_cookie_mode(self):
        original_secure = server.AUTH_COOKIE_SECURE
        server.AUTH_COOKIE_SECURE = True
        try:
            headers = server.clear_auth_cookie_headers()
        finally:
            server.AUTH_COOKIE_SECURE = original_secure

        self.assertEqual(2, len(headers))
        self.assertTrue(all("; Secure" in value for _, value in headers))


class ReleaseSelectionTests(TestCase):
    def test_only_annotated_releases_with_matching_notes_are_listed(self):
        current_sha = "a" * 40
        target_sha = "b" * 40
        tag_names = "\n".join(
            [
                "v1.0.0",
                "v1.1.0",
                "v1.2.0-rc.1",
                "v1.2.0",
                "v2.0.0",
            ]
        )
        annotated = {
            "v1.0.0": True,
            "v1.1.0": False,
            "v1.2.0-rc.1": True,
            "v1.2.0": True,
            "v2.0.0": True,
        }
        notes = {
            "v1.0.0": "初始版本说明",
            "v1.1.0": "轻量标签不应进入列表",
            "v1.2.0-rc.1": "预发布版本需要显式启用",
            "v1.2.0": "",
            "v2.0.0": "正式版本说明",
        }
        shas = {
            "v1.0.0": current_sha,
            "v1.1.0": "c" * 40,
            "v1.2.0-rc.1": "d" * 40,
            "v1.2.0": "e" * 40,
            "v2.0.0": target_sha,
        }

        with (
            mock.patch.object(deploy_webhook, "_git_output", return_value=tag_names),
            mock.patch.object(
                deploy_webhook,
                "_tag_is_annotated",
                side_effect=lambda tag: annotated[tag],
            ),
            mock.patch.object(
                deploy_webhook,
                "_release_notes_for_tag",
                side_effect=lambda tag: notes[tag],
            ),
            mock.patch.object(
                deploy_webhook,
                "_tag_commit_sha",
                side_effect=lambda tag: shas[tag],
            ),
            mock.patch.object(
                deploy_webhook,
                "_commit_details",
                return_value=("2026-08-06T00:00:00+08:00", "release"),
            ),
            mock.patch.object(
                deploy_webhook,
                "_is_ancestor",
                side_effect=lambda ancestor, descendant: ancestor == current_sha,
            ),
        ):
            versions, current, latest = deploy_webhook._available_versions(
                current_sha,
                "origin/main",
                "release",
            )

        self.assertEqual(["v2.0.0", "v1.0.0"], [item["version"] for item in versions])
        self.assertEqual("v1.0.0", current["version"])
        self.assertEqual("v2.0.0", latest["version"])
        self.assertTrue(versions[0]["isSelectable"])
        self.assertFalse(versions[1]["isSelectable"])
        self.assertEqual("正式版本说明", versions[0]["releaseNotes"])

    def test_release_channel_separates_stable_and_beta_versions(self):
        current_sha = "a" * 40
        stable_sha = "b" * 40
        beta_sha = "c" * 40
        tag_names = "\n".join(
            ["v1.2.2", "v1.2.3-alpha.1", "v1.2.3-beta.1", "v1.2.3"]
        )
        tag_shas = {
            "v1.2.2": current_sha,
            "v1.2.3-alpha.1": "d" * 40,
            "v1.2.3-beta.1": beta_sha,
            "v1.2.3": stable_sha,
        }

        with (
            mock.patch.object(deploy_webhook, "_git_output", return_value=tag_names),
            mock.patch.object(deploy_webhook, "_tag_is_annotated", return_value=True),
            mock.patch.object(deploy_webhook, "_release_notes_for_tag", return_value="版本说明"),
            mock.patch.object(
                deploy_webhook,
                "_tag_commit_sha",
                side_effect=lambda tag: tag_shas[tag],
            ),
            mock.patch.object(
                deploy_webhook,
                "_commit_details",
                return_value=("2026-08-13T00:00:00+08:00", "release"),
            ),
            mock.patch.object(
                deploy_webhook,
                "_is_ancestor",
                side_effect=lambda ancestor, descendant: ancestor == current_sha,
            ),
        ):
            release_versions, _, release_latest = deploy_webhook._available_versions(
                current_sha,
                "origin/main",
                "release",
            )
            beta_versions, _, beta_latest = deploy_webhook._available_versions(
                current_sha,
                "origin/main",
                "beta",
            )

        self.assertEqual(["v1.2.3", "v1.2.2"], [item["version"] for item in release_versions])
        self.assertEqual("v1.2.3", release_latest["version"])
        self.assertEqual(["v1.2.3-beta.1"], [item["version"] for item in beta_versions])
        self.assertEqual("v1.2.3-beta.1", beta_latest["version"])
        self.assertTrue(beta_versions[0]["isSelectable"])

    def test_invalid_release_channel_is_rejected(self):
        with self.assertRaises(server.ApiError):
            server.normalize_update_release_channel("nightly")
        with self.assertRaises(ValueError):
            deploy_webhook._normalize_release_channel("nightly")

    def test_repository_url_validation_accepts_github_and_internal_gitea(self):
        valid_urls = [
            "https://github.com/freeisme/asset-center.git",
            "ssh://git@192.0.2.10:2222/organization/office-asset-mgmt.git",
            "git@192.0.2.10:organization/office-asset-mgmt.git",
            "http://localhost:3001/example-org/office-asset-management.git",
        ]

        for repository_url in valid_urls:
            with self.subTest(repository_url=repository_url):
                self.assertEqual(
                    repository_url,
                    server.normalize_update_repository_url(repository_url),
                )
                self.assertEqual(
                    repository_url,
                    deploy_webhook._normalize_repository_url(repository_url),
                )

    def test_repository_url_validation_rejects_credentials_and_local_paths(self):
        invalid_urls = [
            "https://token@github.com/freeisme/asset-center.git",
            "https://user:token@github.com/freeisme/asset-center.git",
            "file:///etc/passwd",
            "ext::sh -c whoami",
            "https://github.com/freeisme/asset-center.git?token=secret",
            "http://github.com/freeisme/asset-center.git",
        ]

        for repository_url in invalid_urls:
            with self.subTest(repository_url=repository_url):
                with self.assertRaises(server.ApiError):
                    server.normalize_update_repository_url(repository_url)
                with self.assertRaises(deploy_webhook.InvalidRepositoryUrlError):
                    deploy_webhook._normalize_repository_url(repository_url)


class VersionGenerationTests(TestCase):
    def test_change_level_maps_patch_minor_and_major(self):
        self.assertEqual("patch", next_version.change_level(["fix: correct recovery"]))
        self.assertEqual("minor", next_version.change_level(["feat: split inventory batches"]))
        self.assertEqual(
            "major",
            next_version.change_level(["refactor!: replace allocation contract"]),
        )
        self.assertEqual(
            "major",
            next_version.change_level(["refactor: update API\n\nBREAKING CHANGE: yes"]),
        )

    def test_next_version_supports_explicit_release_level(self):
        with (
            mock.patch.object(
                next_version,
                "latest_stable_tag",
                return_value=("v2.0.0", (2, 0, 0)),
            ),
            mock.patch.object(next_version, "commit_messages", return_value=[]),
        ):
            self.assertEqual("v2.1.0", next_version.next_version(level="minor")["nextVersion"])
            self.assertEqual("v3.0.0", next_version.next_version(level="major")["nextVersion"])
            self.assertEqual("v2.0.1", next_version.next_version(level="patch")["nextVersion"])


class UpdateFetchTests(TestCase):
    def test_fetch_retries_transient_https_failure_and_syncs_release_tags(self):
        original_attempts = deploy_webhook.GIT_FETCH_ATTEMPTS
        original_retry_seconds = deploy_webhook.GIT_FETCH_RETRY_SECONDS
        transient_error = subprocess.CalledProcessError(
            128,
            ["git", "fetch"],
            stderr="fatal: Failure when receiving data from the peer",
        )
        try:
            deploy_webhook.GIT_FETCH_ATTEMPTS = 3
            deploy_webhook.GIT_FETCH_RETRY_SECONDS = 2
            with (
                mock.patch.object(
                    deploy_webhook.subprocess,
                    "run",
                    side_effect=[
                        transient_error,
                        subprocess.CompletedProcess(["git", "fetch"], 0),
                    ],
                ) as run,
                mock.patch.object(deploy_webhook.time, "sleep") as sleep,
            ):
                deploy_webhook._fetch_repository(
                    "https://github.com/freeisme/asset-center.git",
                    "refs/remotes/update-candidate/main",
                )
        finally:
            deploy_webhook.GIT_FETCH_ATTEMPTS = original_attempts
            deploy_webhook.GIT_FETCH_RETRY_SECONDS = original_retry_seconds

        self.assertEqual(2, run.call_count)
        command = run.call_args_list[0].args[0]
        self.assertIn("http.version=HTTP/1.1", command)
        self.assertIn("http.lowSpeedLimit=1", command)
        self.assertIn("http.lowSpeedTime=120", command)
        self.assertIn("+refs/tags/v*:refs/tags/v*", command)
        self.assertIn(
            "+refs/heads/main:refs/remotes/update-candidate/main",
            command,
        )
        sleep.assert_called_once_with(2)

    def test_fetch_does_not_retry_non_transient_failure(self):
        original_attempts = deploy_webhook.GIT_FETCH_ATTEMPTS
        non_transient_error = subprocess.CalledProcessError(
            128,
            ["git", "fetch"],
            stderr="fatal: repository access denied",
        )
        try:
            deploy_webhook.GIT_FETCH_ATTEMPTS = 3
            with (
                mock.patch.object(
                    deploy_webhook.subprocess,
                    "run",
                    side_effect=non_transient_error,
                ) as run,
                mock.patch.object(deploy_webhook.time, "sleep") as sleep,
            ):
                with self.assertRaises(deploy_webhook.RepositoryFetchError):
                    deploy_webhook._fetch_repository(
                        "https://github.com/freeisme/asset-center.git",
                        "refs/remotes/update-candidate/main",
                    )
        finally:
            deploy_webhook.GIT_FETCH_ATTEMPTS = original_attempts

        self.assertEqual(1, run.call_count)
        sleep.assert_not_called()

    def test_update_service_maps_repository_fetch_failure_to_readable_message(self):
        original_url = server.UPDATE_SERVICE_URL
        original_token = server.UPDATE_CONTROL_TOKEN
        try:
            server.UPDATE_SERVICE_URL = "https://update-service.example.test"
            server.UPDATE_CONTROL_TOKEN = "test-token"
            response = io.BytesIO(
                b'{"ok": false, "error": "repository_fetch_failed"}'
            )
            error = server.HTTPError(
                "https://update-service.example.test/control/status",
                503,
                "Service Unavailable",
                None,
                response,
            )
            with mock.patch.object(server, "urlopen", side_effect=error):
                with self.assertRaisesRegex(
                    server.ApiError,
                    "更新项目无法获取，请检查项目地址",
                ):
                    server.request_update_service()
        finally:
            server.UPDATE_SERVICE_URL = original_url
            server.UPDATE_CONTROL_TOKEN = original_token

    def test_local_gitea_http_repository_maps_to_configured_ssh_origin(self):
        original_http_origin = deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN
        original_ssh_origin = deploy_webhook.LOCAL_GITEA_SSH_ORIGIN
        try:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = "http://198.51.100.10:3001/"
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = "ssh://git@198.51.100.10:2222/"
            self.assertEqual(
                "ssh://git@198.51.100.10:2222/example-org/office-asset-mgmt.git",
                deploy_webhook._fetch_remote_for_repository(
                    "http://198.51.100.10:3001/example-org/office-asset-mgmt.git"
                ),
            )
        finally:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = original_http_origin
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = original_ssh_origin

    def test_local_gitea_mapping_does_not_apply_to_another_origin(self):
        original_http_origin = deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN
        original_ssh_origin = deploy_webhook.LOCAL_GITEA_SSH_ORIGIN
        try:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = "http://198.51.100.10:3001"
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = "ssh://git@198.51.100.10:2222"
            repository_url = "http://198.51.100.11:3001/example-org/office-asset-mgmt.git"
            self.assertEqual(
                repository_url,
                deploy_webhook._fetch_remote_for_repository(repository_url),
            )
        finally:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = original_http_origin
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = original_ssh_origin

    def test_local_gitea_mapping_requires_both_origins(self):
        original_http_origin = deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN
        original_ssh_origin = deploy_webhook.LOCAL_GITEA_SSH_ORIGIN
        try:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = "http://198.51.100.10:3001"
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = ""
            with self.assertRaisesRegex(ValueError, "must be set together"):
                deploy_webhook._fetch_remote_for_repository(
                    "http://198.51.100.10:3001/example-org/office-asset-mgmt.git"
                )
        finally:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = original_http_origin
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = original_ssh_origin

    def test_local_gitea_mapping_can_load_non_secret_origins_from_app_env_file(self):
        original_app_dir = deploy_webhook.APP_DIR
        original_environment = os.environ.get("DEPLOY_LOCAL_GITEA_HTTP_ORIGIN")
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                env_path = Path(temporary_directory) / ".env"
                env_path.write_text(
                    "DEPLOY_LOCAL_GITEA_HTTP_ORIGIN=http://198.51.100.10:3001\n"
                    "DEPLOY_LOCAL_GITEA_SSH_ORIGIN=ssh://git@198.51.100.10:2222\n",
                    encoding="utf-8",
                )
                deploy_webhook.APP_DIR = Path(temporary_directory)
                os.environ.pop("DEPLOY_LOCAL_GITEA_HTTP_ORIGIN", None)
                self.assertEqual(
                    "http://198.51.100.10:3001",
                    deploy_webhook._deployment_setting("DEPLOY_LOCAL_GITEA_HTTP_ORIGIN"),
                )
                self.assertEqual(
                    "ssh://git@198.51.100.10:2222",
                    deploy_webhook._deployment_setting("DEPLOY_LOCAL_GITEA_SSH_ORIGIN"),
                )
        finally:
            deploy_webhook.APP_DIR = original_app_dir
            if original_environment is None:
                os.environ.pop("DEPLOY_LOCAL_GITEA_HTTP_ORIGIN", None)
            else:
                os.environ["DEPLOY_LOCAL_GITEA_HTTP_ORIGIN"] = original_environment

    def test_deployment_environment_passes_local_gitea_mapping_to_update_script(self):
        original_http_origin = deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN
        original_ssh_origin = deploy_webhook.LOCAL_GITEA_SSH_ORIGIN
        try:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = "http://198.51.100.10:3001"
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = "ssh://git@198.51.100.10:2222"
            environment = deploy_webhook._deployment_environment(
                "a" * 40,
                "http://198.51.100.10:3001/example-org/office-asset-mgmt.git",
            )
        finally:
            deploy_webhook.LOCAL_GITEA_HTTP_ORIGIN = original_http_origin
            deploy_webhook.LOCAL_GITEA_SSH_ORIGIN = original_ssh_origin

        self.assertEqual("a" * 40, environment["DEPLOY_TARGET_SHA"])
        self.assertEqual(
            "http://198.51.100.10:3001/example-org/office-asset-mgmt.git",
            environment["DEPLOY_REPOSITORY_URL"],
        )
        self.assertEqual(
            "http://198.51.100.10:3001",
            environment["DEPLOY_LOCAL_GITEA_HTTP_ORIGIN"],
        )
        self.assertEqual(
            "ssh://git@198.51.100.10:2222",
            environment["DEPLOY_LOCAL_GITEA_SSH_ORIGIN"],
        )


class DeploymentScriptTests(TestCase):
    def test_repository_layout_has_canonical_paths_and_compatibility_entries(self):
        self.assertTrue((ROOT / "database" / "bootstrap").is_dir())
        self.assertTrue((ROOT / "database" / "migrations").is_dir())
        self.assertTrue((ROOT / "database" / "manual").is_dir())
        self.assertTrue((ROOT / "tools" / "migration_runner.py").is_file())
        self.assertTrue((ROOT / "scripts" / "windows" / "deploy.ps1").is_file())
        self.assertTrue((ROOT / "docs" / "README.md").is_file())

        runner = (ROOT / "tools" / "migration_runner.py").read_text(encoding="utf-8")
        self.assertIn('ROOT_DIR = Path(__file__).resolve().parents[1]', runner)
        self.assertIn('ROOT_DIR / "database" / "migrations"', runner)

        root_runner = (ROOT / "migration_runner.py").read_text(encoding="utf-8")
        root_deploy = (ROOT / "deploy.ps1").read_text(encoding="utf-8")
        windows_deploy = (ROOT / "scripts" / "windows" / "deploy.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("from tools.migration_runner import main", root_runner)
        self.assertIn('scripts\\windows\\deploy.ps1', root_deploy)
        self.assertIn('[Alias("DbName")][string]$Database', windows_deploy)
        self.assertNotIn('[Alias("DbName")][string]$DbName', windows_deploy)
        self.assertIn("$lastLine = $result | Select-Object -Last 1", windows_deploy)
        self.assertIn("if ($null -eq $lastLine)", windows_deploy)

    def test_backup_script_uses_atomic_private_output(self):
        script = (ROOT / "deploy" / "scripts" / "backup_database.sh").read_text(
            encoding="utf-8"
        )

        for option in ("--skip-lock-tables", "--no-tablespaces", "--hex-blob"):
            self.assertIn(option, script)
        self.assertIn("temporary_file=\"$(mktemp", script)
        self.assertIn('mv -- "${temporary_file}" "${backup_file}"', script)
        self.assertNotIn('> "${backup_file}"', script)

    def test_compose_backup_script_uses_deployment_user_home_and_atomic_output(self):
        script = (ROOT / "deploy" / "scripts" / "backup_compose_database.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('${HOME:-/tmp}/backups/office-asset-mgmt', script)
        self.assertIn('docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" exec -T db', script)
        self.assertIn('sql_temporary_file="$(mktemp', script)
        self.assertIn('gzip --stdout -- "${sql_temporary_file}" > "${archive_temporary_file}"', script)
        self.assertIn('sha256sum "${archive_temporary_file}" > "${checksum_temporary_file}"', script)
        self.assertIn('mv -- "${archive_temporary_file}" "${backup_file}"', script)
        self.assertIn('mv -- "${checksum_temporary_file}" "${checksum_file}"', script)

    def test_docker_initializer_does_not_put_root_password_in_arguments(self):
        script = (ROOT / "deploy" / "docker" / "init_database.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn('export MYSQL_PWD="${MYSQL_ROOT_PASSWORD}"', script)
        self.assertNotIn('"--password=${MYSQL_ROOT_PASSWORD}"', script)
        self.assertIn("22_update_repository_setting.sql", script)

    def test_compose_healthcheck_keeps_mysql_password_out_of_arguments(self):
        compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        docker_doc = (ROOT / "docs" / "deployment" / "docker.md").read_text(
            encoding="utf-8"
        )

        self.assertIn('MYSQL_PWD=\\"$$MYSQL_PASSWORD\\" mysql', compose)
        self.assertNotIn('-p"$$MYSQL_PASSWORD"', compose)
        self.assertNotIn('-p"$MYSQL_PASSWORD"', docker_doc)

    def test_security_migration_adds_session_provenance_columns(self):
        migration = (
            ROOT / "database" / "bootstrap" / "21_security_hardening.sql"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn("ADD COLUMN ip_address VARCHAR(64)", migration)
        self.assertIn("ADD COLUMN user_agent VARCHAR(500)", migration)

    def test_legacy_security_compatibility_migration_is_first_and_idempotent(self):
        migration_path = (
            ROOT
            / "database"
            / "migrations"
            / "20260813_001_legacy_security_compatibility.sql"
        )
        migration = migration_path.read_text(encoding="utf-8")
        discovered = migration_runner.discover_migrations()

        self.assertEqual(migration_path, discovered[0].path)
        self.assertIn("CREATE TABLE IF NOT EXISTS auth_bootstrap_guard", migration)
        self.assertIn("ADD COLUMN ip_address VARCHAR(64)", migration)
        self.assertIn("ADD COLUMN user_agent VARCHAR(500)", migration)
        self.assertIn("table_name = 'auth_session') = 1", migration)

    def test_update_repository_setting_migration_exists(self):
        migration = (
            ROOT / "database" / "bootstrap" / "22_update_repository_setting.sql"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn("update_repository_url", migration)
        self.assertIn("ON DUPLICATE KEY UPDATE", migration)

    def test_update_script_can_fetch_selected_repository_url(self):
        script = (ROOT / "deploy" / "scripts" / "update_from_gitea.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("DEPLOY_REPOSITORY_URL", script)
        self.assertIn("DEPLOY_LOCAL_GITEA_HTTP_ORIGIN", script)
        self.assertIn("DEPLOY_LOCAL_GITEA_SSH_ORIGIN", script)
        self.assertIn("fetch_repository()", script)
        self.assertIn("fetch_remote_for_repository()", script)
        self.assertIn("http.version=HTTP/1.1", script)
        self.assertIn("http.lowSpeedLimit=1", script)
        self.assertIn("http.lowSpeedTime=120", script)
        self.assertIn('"+refs/tags/v*:refs/tags/v*"', script)
        self.assertIn("DEPLOY_GIT_FETCH_ATTEMPTS", script)
        self.assertIn("DEPLOY_GIT_FETCH_RETRY_SECONDS", script)
        self.assertIn('build --pull app migrate', script)
        self.assertIn('up -d --wait --no-deps db', script)
        self.assertIn('stop app || true', script)
        self.assertIn('run --rm --no-deps -T migrate', script)
        self.assertIn('up -d --no-deps --remove-orphans app', script)
        self.assertNotIn('docker compose "${compose_args[@]}" up -d --remove-orphans', script)


class MigrationBaselineTests(TestCase):
    def test_existing_database_requires_explicit_baseline_adoption(self):
        with (
            mock.patch.object(migration_runner, "table_exists", return_value=False),
            mock.patch.object(migration_runner, "has_existing_business_tables", return_value=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "schema_migration registry"):
                migration_runner.prepare_migration_registry("office_asset_mgmt")

    def test_baseline_adoption_validates_legacy_schema_before_writing_registry(self):
        with (
            mock.patch.object(migration_runner, "table_exists", return_value=False),
            mock.patch.object(migration_runner, "has_existing_business_tables", return_value=True),
            mock.patch.object(
                migration_runner,
                "missing_tables",
                return_value=["auth_session"],
            ),
            mock.patch.object(migration_runner, "ensure_registry") as ensure_registry,
            mock.patch.object(migration_runner, "mark_baseline") as mark_baseline,
        ):
            with self.assertRaisesRegex(RuntimeError, "missing required tables"):
                migration_runner.prepare_migration_registry(
                    "office_asset_mgmt",
                    migration_runner.LEGACY_BASELINE_VERSION,
                )
            ensure_registry.assert_not_called()
            mark_baseline.assert_not_called()

    def test_legacy_baseline_does_not_require_compatible_security_guard(self):
        self.assertIn("auth_session", migration_runner.LEGACY_BASELINE_REQUIRED_TABLES)
        self.assertNotIn(
            "auth_bootstrap_guard",
            migration_runner.LEGACY_BASELINE_REQUIRED_TABLES,
        )

    def test_baseline_adoption_records_only_verified_legacy_baseline(self):
        with (
            mock.patch.object(migration_runner, "table_exists", return_value=False),
            mock.patch.object(migration_runner, "has_existing_business_tables", return_value=True),
            mock.patch.object(migration_runner, "missing_tables", return_value=[]),
            mock.patch.object(migration_runner, "ensure_registry") as ensure_registry,
            mock.patch.object(migration_runner, "mark_baseline") as mark_baseline,
        ):
            migration_runner.prepare_migration_registry(
                "office_asset_mgmt",
                migration_runner.LEGACY_BASELINE_VERSION,
            )

        ensure_registry.assert_called_once_with("office_asset_mgmt")
        mark_baseline.assert_called_once_with(
            "office_asset_mgmt",
            migration_runner.LEGACY_BASELINE_VERSION,
        )

    def test_only_the_known_legacy_baseline_can_be_adopted(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported baseline"):
            migration_runner.validate_legacy_baseline(
                "office_asset_mgmt",
                "legacy-unknown",
            )

    def test_version_notes_use_semver_headings(self):
        notes = (ROOT / "VERSION_NOTES.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (v\S+)$", notes, flags=re.MULTILINE)

        self.assertTrue(headings)
        self.assertTrue(
            all(
                re.fullmatch(
                    r"v\d+\.\d+\.\d+(?:-beta\.(?:0|[1-9]\d*))?",
                    item,
                )
                for item in headings
            )
        )

    def test_update_panel_has_release_channel_and_motion_support(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("DEFAULT_UPDATE_RELEASE_CHANNEL = \"beta\"", app)
        self.assertIn('data-update-release-channel', app)
        self.assertIn("releaseChannel", app)
        self.assertIn("page-enter", app)
        self.assertIn(".update-channel-row", styles)
        self.assertIn("@keyframes page-content-enter", styles)
        self.assertIn("prefers-reduced-motion", styles)


class FrontendAccessibilityAndThemeTests(TestCase):
    def test_settings_navigation_uses_cached_state_and_only_animates_page_changes(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("let lastRenderedPage = \"\";", app)
        self.assertIn("const isPageTransition = lastRenderedPage !== state.page;", app)
        self.assertIn(
            '<div${isPageTransition ? \' class="page-enter"\' : ""}>${renderPage()}</div>',
            app,
        )
        self.assertIn('if (state.page === "settings" && !settingsState.loaded)', app)
        self.assertIn("function renderIfCurrentPage(page)", app)
        self.assertIn('const targetPage = actionElement.dataset.page || "dashboard";', app)
        self.assertIn("if (targetPage === state.page) return;", app)
        self.assertIn("function syncSettingsTabsAndContent()", app)
        self.assertIn("currentTabs.replaceWith(nextTabs);", app)
        self.assertIn("currentContent.replaceWith(nextContent);", app)
        self.assertIn("if (!syncSettingsTabsAndContent()) {", app)
        for page in ("settings", "audit", "tickets", "serviceManagement", "governance", "formDesigner"):
            self.assertIn(f'renderIfCurrentPage("{page}")', app)

    def test_async_page_loads_ignore_stale_responses(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("const latestAsyncRequests = new Map();", app)
        self.assertIn("function beginAsyncRequest(key)", app)
        self.assertIn("function isLatestAsyncRequest(key, requestId)", app)
        self.assertIn("function invalidateAsyncRequests()", app)
        for request_key in (
            "audit-logs",
            "access-control-target",
            "tickets",
            "governance",
            "service-management",
            "form-designer",
        ):
            self.assertIn(f'beginAsyncRequest("{request_key}")', app)
        self.assertNotIn(".then(render)", app)

    def test_form_controls_expose_label_associations_and_permission_names(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function createControlId(name)", app)
        self.assertIn('<label for="${controlId}">', app)
        self.assertIn('<select id="${controlId}" name="${escapeHtml(', app)
        self.assertIn('id="access-target-type" data-access-target-type', app)
        self.assertIn('id="access-target-id" data-access-target-id', app)
        self.assertIn("const permissionModuleLabels =", app)
        self.assertIn("function normalizePermissionModuleName(rawName, code)", app)
        self.assertIn("function permissionModuleLabel(module)", app)
        self.assertIn("const mapped = permissionModuleLabels[code];", app)
        self.assertIn("return normalized || code;", app)
        self.assertIn('aria-label="${escapeHtml(`${permissionModuleLabel(row.module)}', app)
        self.assertIn("function readonlyField(label, value)", app)
        labels_without_for = re.findall(
            r"<label(?![^>]*\bfor=)[^>]*>(?:(?!</label>)[\s\S])*?</label>",
            app,
        )
        self.assertTrue(labels_without_for)
        for label in labels_without_for:
            self.assertRegex(label, r"<(?:input|select|textarea)\b")

    def test_theme_preserves_existing_accents_with_targeted_contrast_repairs(self):
        styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("v2.0.5 targeted visual repairs", styles)
        self.assertIn("--canvas: #000000;", styles)
        self.assertIn("html[data-theme=\"dark\"] .sidebar", styles)
        self.assertIn("background: #000000 !important;", styles)
        self.assertIn("html[data-theme=\"dark\"] .device-chip {", styles)
        self.assertIn("background: #0b0b0b !important;", styles)
        self.assertIn("html[data-theme=\"dark\"] .device-chip small {", styles)
        self.assertIn("html:not([data-theme=\"dark\"]) .inventory-node-main strong,", styles)
        self.assertIn("html:not([data-theme=\"dark\"]) .inventory-node-main span,", styles)
        self.assertIn("html[data-theme=\"dark\"] .inventory-panel,", styles)
        self.assertIn("html[data-theme=\"dark\"] .inventory-node-main strong,", styles)
        self.assertIn("html[data-theme=\"dark\"] .designer-workspace,", styles)
        self.assertIn("background: #7367f0 !important;", styles)
        self.assertIn("background: #252336 !important;", styles)
        self.assertIn("html:not([data-theme=\"dark\"]) .form-field label", styles)
        self.assertIn("color: var(--ink) !important;", styles)


class EmployeeWorkflowUiTests(TestCase):
    def test_employee_editor_does_not_collect_offboarding_details(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        editor = app.split("function openEmployeeModal", 1)[1].split(
            "\nfunction leftEmployeeReadonlyField",
            1,
        )[0]

        self.assertIn('["active", "inactive"].map', editor)
        self.assertNotIn('"left"', editor)
        self.assertNotIn("data-left-fields", editor)
        self.assertNotIn('"leaveDate"', editor)
        self.assertNotIn('"leaveInfo"', editor)
        self.assertNotIn('"leaveRemark"', editor)
        self.assertIn("function openLeftEmployeeModal", app)
        self.assertIn("离职时设备快照", app)

    def test_employee_offboarding_is_an_independent_backend_command(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        server_source = (ROOT / "server.py").read_text(encoding="utf-8")

        self.assertIn('const API_EMPLOYEES_URL = "/api/employees";', app)
        self.assertIn('data-action="open-employee-offboard"', app)
        self.assertIn('data-form="employee-offboard"', app)
        self.assertIn("function handleEmployeeOffboardSubmit", app)
        self.assertIn("${API_EMPLOYEES_URL}/${encodeURIComponent(employeeId)}/offboard", app)
        self.assertIn("请通过“办理离职”表单提交受控离职流程。", app)
        self.assertNotIn("const archived = archiveEmployee(pending.employee", app)

        self.assertIn("/api/employees/", router)
        self.assertIn("/offboard", router)
        self.assertIn('self._write_context(handler, "employees", "update")', router)
        self.assertIn("offboard_employee", router)

        self.assertIn("def offboard_employee(", service)
        self.assertIn('"recover": "回收"', service)
        self.assertIn("办理离职需要使用人员的全部数据或所属部门数据权限。", service)
        self.assertIn("left_employee_archive", service)
        self.assertIn("UPDATE auth_session session", service)
        self.assertIn("SET employee_id = NULL", service)
        self.assertIn("service_notification", service)
        self.assertIn("employee_offboarded", service)
        self.assertIn("api_idempotency_key", service)
        self.assertIn('"employee_offboarded": "办理离职"', server_source)

    def test_employee_offboarding_requires_complete_item_handling(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("离职日期、离职原因和备注不能为空。", service)
        self.assertIn("当前名下资产或物资必须逐项处理后才能办理离职。", service)
        self.assertIn("异常待处理必须填写说明。", service)
        self.assertIn("转交他人时必须选择接收人员。", service)
        self.assertIn("离职资产只能转交给在职人员。", service)
        self.assertIn("离职办理异常待处理", service)
        self.assertIn("离职办理转交给", service)
        self.assertIn("离职办理回收入库", service)
        self.assertIn("current_keys != submitted_key_set", service)
        self.assertIn("@current_item_count = {len(plan)}", service)
        self.assertIn("allocation.stock_adjusted = 1", service)
        self.assertIn("trigger_action", service)
        self.assertIn("targetEmployeeName", app)
        self.assertIn("leftEmployeeDeviceActionText", app)
        self.assertIn("异常待处理必须填写说明。", app)


class FlowRecordUiTests(TestCase):
    def test_flow_page_has_filters_export_classification_and_inline_notes(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-page="flowControl"', index)
        self.assertIn("<span>物资流转记录</span>", index)
        self.assertIn("function renderFlowControlRecordTable(logs)", app)
        self.assertIn("function renderFlowRecordNoteEditor(log)", app)
        self.assertIn("function getFilteredFlowRecords()", app)
        self.assertIn("function exportFlowRecords()", app)
        self.assertIn('data-action="export-flow-records"', app)
        self.assertIn('data-action="clear-flow-record-filters"', app)
        self.assertIn('data-filter="flowSearch"', app)
        self.assertIn('data-filter="flowEmployee"', app)
        self.assertIn('data-filter="flowStartDate"', app)
        self.assertIn('data-filter="flowEndDate"', app)
        self.assertIn('data-form="inventory-log-note-correction"', app)
        self.assertIn("/api/inventory/movement-logs/${encodeURIComponent(log.id)}/note-corrections", app)
        self.assertIn("correctionReason", app)
        self.assertNotIn("流转日志为事务结果，只能通过新的业务命令产生，暂不支持单独改写。", app)
        self.assertIn('  return: { label: "归还回收"', app)
        self.assertIn('category: "库存入库"', app)
        self.assertIn('category: "领用发放"', app)
        self.assertIn('category: "归还回收"', app)
        self.assertNotIn('data-form="flow-control"', app)
        self.assertNotIn("登记物资调动", app)

    def test_text_filters_use_drafts_until_explicitly_applied(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        active_inventory_renderer = app.split("function renderInventoryPage() {", 1)[1].split(
            "\nfunction renderFlowRecordNoteEditor",
            1,
        )[0]

        self.assertIn("const deferredTextFilterNames = new Set([", app)
        self.assertIn("function filterSearchDraftValue(filterName)", app)
        self.assertIn("function applyDeferredTextFilters(filterNames)", app)
        self.assertIn("function applyInventorySearchFilter()", app)
        self.assertIn("function applyFlowRecordFilters()", app)
        self.assertIn("function applyAuditFilters()", app)
        self.assertIn('data-action="apply-inventory-search"', app)
        self.assertIn('data-action="apply-flow-record-filters"', app)
        self.assertIn('filterSearchDraftValue("inventorySearch")', active_inventory_renderer)
        self.assertIn('data-action="apply-inventory-search"', active_inventory_renderer)
        self.assertIn('filterSearchDrafts[filterName] = filter.value;', app)
        self.assertIn('if (String(filterName).startsWith("audit")) {', app)
        self.assertIn("refreshAuditLogs({ silent: true })", app)
        self.assertNotIn("renderPreservingFilterInput", app)
        self.assertNotIn("queueAuditLogRefresh", app)

    def test_movement_note_corrections_are_append_only_and_audited(self):
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        state_reader = (ROOT / "server.py").read_text(encoding="utf-8")

        self.assertIn("/api/inventory/movement-logs/", router)
        self.assertIn("/note-corrections", router)
        self.assertIn("add_inventory_movement_note_correction", service)
        self.assertIn("START TRANSACTION", service)
        self.assertIn("inventory_movement_note_correction", service)
        self.assertIn("inventory_movement_note_corrected", service)
        self.assertNotIn("UPDATE inventory_movement_log SET note", service)
        self.assertIn("'originalNote'", state_reader)
        self.assertIn("'effectiveNote'", state_reader)
        self.assertIn("'noteCorrections'", state_reader)


class DataQualityRegressionTests(TestCase):
    def test_quality_outputs_are_chinese_and_resolution_requires_a_result(self):
        operations = (ROOT / "office_asset" / "operations.py").read_text(encoding="utf-8")
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('"high": "高"', operations)
        self.assertIn('"computer": "办公终端"', operations)
        self.assertIn('"resolved": "已解决"', operations)
        self.assertIn("请填写处理结果后再解决问题。", operations)
        self.assertIn("resolution_result", operations)
        self.assertIn("data_quality_issue_resolved", operations)
        self.assertIn('self._write_context(handler, "quality", "approve")', router)
        self.assertIn('data-form="quality-issue-resolution"', app)
        self.assertIn("处理结果", app)
        self.assertIn('{ resolutionResult }', app)
        self.assertIn('hasPermission("quality", "approve")', app)

    def test_quality_resolution_migration_is_retry_safe(self):
        migration = (
            ROOT
            / "database"
            / "migrations"
            / "20260827_001_flow_note_corrections_and_quality_resolution.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_movement_note_correction", migration)
        self.assertIn("information_schema.columns", migration)
        self.assertIn("resolution_result", migration)


class InventoryRecoveryRegressionTests(TestCase):
    def test_inventory_model_identity_is_used_for_allocations_and_recovery(self):
        bootstrap = (
            ROOT / "database" / "bootstrap" / "01_schema.sql"
        ).read_text(encoding="utf-8")
        compatibility_migration = (
            ROOT
            / "database"
            / "migrations"
            / "20260907_000_usage_inventory_model_identity_compatibility.sql"
        ).read_text(encoding="utf-8")
        migration = (
            ROOT
            / "database"
            / "migrations"
            / "20260907_001_usage_inventory_model_identity.sql"
        ).read_text(encoding="utf-8")
        individual_usage_migration = (
            ROOT
            / "database"
            / "migrations"
            / "20260909_001_individual_inventory_usage_records.sql"
        ).read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        allocation_source = service.split("    def allocate_inventory(", 1)[1].split(
            "\n    def adjust_inventory(",
            1,
        )[0]
        offboard_source = service.split("    def offboard_employee(", 1)[1]

        self.assertIn("inventory_model_key", bootstrap)
        self.assertIn("GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL", bootstrap)
        self.assertIn("KEY idx_non_asset_usage_item_model", bootstrap)
        self.assertIn("KEY idx_employee_monitor_model", bootstrap)
        self.assertNotIn("UNIQUE KEY uq_non_asset_usage_item_model", bootstrap)
        self.assertNotIn("UNIQUE KEY uq_employee_monitor_model", bootstrap)
        self.assertIn("GENERATED ALWAYS AS (COALESCE(inventory_model_id, 0)) VIRTUAL", compatibility_migration)
        self.assertTrue(
            (
                ROOT
                / "database"
                / "migrations"
                / "20260907_000_usage_inventory_model_identity_compatibility.sql"
            ).is_file()
        )
        self.assertIn("ADD COLUMN inventory_model_key", migration)
        self.assertIn("ADD UNIQUE KEY uq_non_asset_usage_item_model", migration)
        self.assertIn("ADD UNIQUE KEY uq_employee_monitor_model", migration)
        discovered_versions = [item.version for item in migration_runner.discover_migrations()]
        self.assertLess(
            discovered_versions.index("20260907_000_usage_inventory_model_identity_compatibility"),
            discovered_versions.index("20260907_001_usage_inventory_model_identity"),
        )
        self.assertLess(
            migration.index("ADD UNIQUE KEY uq_non_asset_usage_item_model"),
            migration.index("DROP INDEX uq_non_asset_usage_item"),
        )
        self.assertLess(
            migration.index("ADD UNIQUE KEY uq_employee_monitor_model"),
            migration.index("DROP INDEX uq_employee_monitor"),
        )
        self.assertIn("DROP INDEX uq_non_asset_usage_item_model", individual_usage_migration)
        self.assertIn("DROP INDEX uq_employee_monitor_model", individual_usage_migration)
        self.assertIn("ADD KEY idx_non_asset_usage_item_model", individual_usage_migration)
        self.assertIn("ADD KEY idx_employee_monitor_model", individual_usage_migration)
        self.assertLess(
            discovered_versions.index("20260907_001_usage_inventory_model_identity"),
            discovered_versions.index("20260909_001_individual_inventory_usage_records"),
        )
        self.assertIn('model_id_sql = "NULL"', allocation_source)
        self.assertNotIn("quantity = quantity + 1", allocation_source)
        self.assertNotIn("quantity = quantity + VALUES(quantity)", allocation_source)
        self.assertIn(
            "SET @usage_ref = IF(@stock_updated = 1, LAST_INSERT_ID(), 0);",
            allocation_source,
        )
        self.assertIn("allocation_groups: dict[int, dict[str, int]]", offboard_source)
        self.assertIn("inventory_model_id <=> {group_model_id_sql}", offboard_source)
        self.assertIn("GROUP BY allocation.inventory_model_id", offboard_source)
        self.assertIn("allocation.stock_adjusted = 1", offboard_source)
        # 登记物资（未扣库存）现在同样回收入库，缺少型号时自动补齐目录。
        self.assertIn("@allocation_recovery_quantity = 0", offboard_source)
        self.assertIn("AND @recovery_model_id > 0", offboard_source)
        self.assertIn("_recovery_catalog_sql", offboard_source)
        self.assertNotIn("显示屏品牌型号重复", server_source := (ROOT / "server.py").read_text(encoding="utf-8"))
        self.assertNotIn("非资产设备品牌型号重复", server_source)

    def test_register_without_deduction_honors_json_false(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        allocation_source = service.split("    def allocate_inventory(", 1)[1].split(
            "\n    def adjust_inventory(",
            1,
        )[0]

        self.assertIn('stock_adjusted = parse_bool(payload.get("stockAdjusted"), True)', allocation_source)
        self.assertIn('if stock_adjusted:\n                raise self.api_error("Inventory deduction requires a registered inventory model.")', allocation_source)
        self.assertIn('model_id_sql = "NULL"', allocation_source)
        self.assertIn('if model_id > 0:', allocation_source)
        self.assertIn('if allocation_type == "monitor":', allocation_source)
        self.assertNotIn('self.db.text(payload.get("stockAdjusted"))', allocation_source)
        self.assertFalse(server.parse_bool(False, True))
        self.assertTrue(server.parse_bool(None, True))

    def test_computer_submit_uses_server_assignment_flow(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        source = app.split("async function handleComputerSubmit(form) {", 1)[1].split(
            "\nasync function handleEmployeeSubmit(form) {",
            1,
        )[0]

        self.assertIn("requestJson(API_STATE_URL)", source)
        self.assertIn("sameRecordId(computer.id, id)", source)
        self.assertIn("const shouldAssign = Boolean(desiredUserId)", source)
        self.assertIn("/api/computers/${encodeURIComponent(computerId)}/assignments", source)
        self.assertIn("/api/computers/${encodeURIComponent(computerId)}/assignments/return", source)
        self.assertIn('const statusForSave = desiredUserId ? "in_use" : shouldReturn ? currentStatus : targetStatus;', source)

    def test_custom_inventory_registration_keeps_fallback_brand_and_model_names(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        return_source = service.split("    def return_inventory(", 1)[1].split(
            "\n    def return_usage_inventory(",
            1,
        )[0]
        usage_source = service.split("    def return_usage_inventory(", 1)[1].split(
            "\n    def list_allocations(",
            1,
        )[0]
        list_source = service.split("    def list_allocations(", 1)[1].split(
            "\n    def _sql_id_list(",
            1,
        )[0]

        self.assertIn("monitor_usage.display_name", return_source)
        self.assertIn("non_asset_usage.brand", return_source)
        self.assertIn("usage_row.display_name", usage_source)
        self.assertIn("usage_row.model", usage_source)
        self.assertIn("monitor_usage.display_name", list_source)
        self.assertIn("non_asset_usage.brand", list_source)

    def test_device_save_allows_custom_registration_without_inventory_model(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        source = app.split("async function finishDeviceSave(mode) {", 1)[1].split(
            "\nasync function handleRoleCreateSubmit(form) {",
            1,
        )[0]

        self.assertIn('if (mode === "deduct" && !model)', source)
        self.assertIn('if (mode === "deduct" && !sourceWarehouseId)', source)
        self.assertIn("returnWarehouseId", source)
        self.assertIn("warehouseId: mode === \"deduct\" ? sourceWarehouseId : \"\"", source)
        self.assertIn("pending.previous.stockAdjusted ? returnWarehouseId : \"\"", source)
        self.assertIn('modelId: model?.id || ""', source)
        self.assertIn('typeId: pending.item.typeId || ""', source)
        self.assertIn('inventoryBrandId: pending.item.inventoryBrandId || ""', source)
        self.assertIn('brand: brandName', source)
        self.assertIn('model: modelName', source)
        self.assertIn('displayName: pending.kind === "monitor" ? brandName : ""', source)
        self.assertIn('stockAdjusted: mode === "deduct"', source)

    def test_recovery_selection_matches_numeric_and_string_ids(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function sameRecordId(left, right)", app)
        self.assertIn("state.employees.find((employee) => sameRecordId(employee.id, id))", app)
        recovery_source = app.split("function recoveryDeviceFromSelection", 1)[1].split(
            "\nfunction openDeviceRecoveryConfirm",
            1,
        )[0]
        self.assertGreaterEqual(recovery_source.count("sameRecordId("), 2)
        self.assertIn("const selectedId = String(id);", recovery_source)

    def test_recovery_keeps_only_unprocessed_devices_after_partial_failure(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        recovery_source = app.split("async function confirmDeviceRecovery", 1)[1].split(
            "\nfunction openLeaveRecoveryModal",
            1,
        )[0]

        self.assertIn("let remainingDevices = [...pending.devices];", recovery_source)
        self.assertIn("remainingDevices = pending.devices.slice(index + 1);", recovery_source)
        self.assertIn("devices: remainingDevices", recovery_source)
        self.assertIn("if (!remainingDevices.length)", recovery_source)
        self.assertIn(
            "openDeviceRecoveryConfirm(pending.employeeId, pending.kind, remainingDevices, warehouseId)",
            recovery_source,
        )

    def test_inventory_operations_use_scoped_default_warehouses(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        allocation_return = service.split("    def return_inventory(", 1)[1].split(
            "\n    def return_usage_inventory(",
            1,
        )[0]
        legacy_return = service.split("    def return_usage_inventory(", 1)[1].split(
            "\n    def list_allocations(",
            1,
        )[0]
        offboard_normalization = service.split("    def _normalize_offboarding_plan(", 1)[1].split(
            "\n    def offboard_employee(",
            1,
        )[0]

        self.assertIn('data-form="device-recovery"', app)
        self.assertIn('warehouseSelectField(', app)
        self.assertIn('"回收目标仓库"', app)
        self.assertIn("data-offboard-recovery-warehouse", app)
        self.assertIn("data-stock-adjusted", app)
        self.assertIn('name="sourceWarehouseId"', app)
        self.assertIn('name="returnWarehouseId"', app)
        self.assertIn('preferred_org_id=employee.get("orgId")', service)
        self.assertIn("preferred_org_id=self._actor_org_id(context)", allocation_return)
        self.assertIn("preferred_org_id=self._actor_org_id(context)", legacy_return)
        self.assertIn("require_explicit=True", offboard_normalization)
        self.assertIn("function defaultWarehouseIdForOrg(orgId)", app)
        self.assertIn('["registrationMode", "warehouseId", "computerInventoryModelId"]', app)
        self.assertIn("选择回收时必须指定回收目标仓库。", offboard_normalization)
        self.assertIn("Every recovery must name its destination warehouse", offboard_normalization)
        self.assertIn(
            "ON DUPLICATE KEY UPDATE quantity = inventory_warehouse_stock.quantity",
            allocation_return,
        )
        self.assertIn(
            "ON DUPLICATE KEY UPDATE quantity = inventory_warehouse_stock.quantity",
            legacy_return,
        )

    def test_computer_registration_has_custom_and_warehouse_modes(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")

        self.assertIn('{ value: "custom", label: "自定义品牌型号" }', app)
        self.assertIn('{ value: "warehouse", label: "从仓库库存登记" }', app)
        self.assertIn("computerInventoryModelOptionsForWarehouse", app)
        self.assertIn("modelSelect.required = warehouseMode", app)
        self.assertIn("modelSelect.disabled = !warehouseMode", app)
        self.assertIn("if (model.batchKey) parts.push(`批次：${model.batchKey}`);", app)
        self.assertIn('registration_mode == "warehouse"', service)
        self.assertIn("The selected warehouse does not have enough inventory.", service)
        self.assertIn("inventory_stock_adjusted", service)
        self.assertIn("inventoryStockAdjusted", service)
        self.assertIn('preferred_org_id=employee.get("orgId")', service)

    def test_legacy_usage_return_has_compatibility_route_and_transactional_guards(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")

        self.assertIn("/api/inventory/usage/${encodeURIComponent(allocationType)}/", app)
        self.assertIn("if (matches.length) return recoveryRecords;", app)
        self.assertIn('if path.startswith("/api/inventory/usage/")', router)
        self.assertIn("len(parts) != 7", router)
        self.assertIn("def return_usage_inventory(", service)
        self.assertIn("START TRANSACTION;", service)
        self.assertIn("ORDER BY allocation_id DESC", service)
        self.assertIn("LIMIT 1", service)
        self.assertIn("FOR UPDATE;", service)
        self.assertIn("Legacy usage reconciled during return.", service)

    def test_inventory_returns_do_not_write_zero_quantity_usage_rows(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        allocation_return = service.split("    def return_inventory(", 1)[1].split(
            "\n    def return_usage_inventory(",
            1,
        )[0]
        legacy_return = service.split("    def return_usage_inventory(", 1)[1].split(
            "\n    def list_allocations(",
            1,
        )[0]

        self.assertIn("SET @usage_quantity = 0;", allocation_return)
        self.assertIn("AND quantity > {quantity}", allocation_return)
        self.assertIn("AND quantity = {quantity}", allocation_return)
        self.assertNotIn("SET quantity = quantity - @usage_quantity", legacy_return)
        self.assertIn("DELETE FROM {usage_table}", legacy_return)
        self.assertIn("AND quantity = @usage_quantity", legacy_return)


class ScrapManagementRegressionTests(TestCase):
    def test_scrap_migration_is_incremental_and_never_destroys_history(self):
        migration = (
            ROOT / "database" / "migrations" / "20260915_001_scrap_management.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS scrap_reason", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_scrap_record", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS asset_scrap_record", migration)
        self.assertIn("information_schema.columns", migration)
        self.assertIn("information_schema.table_constraints", migration)
        self.assertIn("ADD COLUMN is_archived TINYINT(1) NOT NULL DEFAULT 0", migration)
        self.assertIn("CHECK (status IN ('active', 'returned', 'cancelled', 'scrapped'))", migration)
        self.assertIn("'scrap_management', '报废管理'", migration)
        self.assertIn("INSERT INTO auth_role_permission", migration)
        self.assertNotIn("DROP TABLE", migration.upper())
        self.assertNotIn("DROP COLUMN is_active", migration.upper())
        self.assertNotIn("DELETE FROM employee_monitor_usage", migration)
        self.assertNotIn("DELETE FROM employee_non_asset_usage", migration)
        self.assertNotIn("DELETE FROM computer_asset", migration)

    def test_scrap_routes_require_dedicated_permissions_and_commands(self):
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")

        self.assertIn('path.endswith("/scrap") and method == "POST"', router)
        self.assertIn('self._write_context(handler, "scrap_management", "create")', router)
        self.assertIn('self.deps.require_permission(context, "inventory_operations", "view")', router)
        self.assertIn('self.deps.require_permission(context, "it_assets", "view")', router)
        self.assertIn('path == "/api/scrap-records" and method == "GET"', router)
        self.assertIn('path.startswith("/api/scrap-records/") and method == "GET"', router)
        self.assertIn('path == "/api/scrap-reasons" and method == "GET"', router)
        self.assertIn('self._read_context(handler, "scrap_management")', router)
        self.assertIn("self.assets.scrap_inventory_usage(", router)
        self.assertIn("self.assets.scrap_computer(", router)

    def test_inventory_scrap_never_restores_stock_and_keeps_the_usage_row(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        inventory_scrap = service.split("    def scrap_inventory_usage(", 1)[1].split(
            "\n    def scrap_computer(",
            1,
        )[0]

        self.assertIn("START TRANSACTION;", inventory_scrap)
        self.assertIn("FOR UPDATE;", inventory_scrap)
        self.assertIn("SET @scrap_allowed = IF(", inventory_scrap)
        self.assertIn("SET is_active = 0", inventory_scrap)
        self.assertIn("SET status = 'scrapped'", inventory_scrap)
        self.assertIn("INSERT INTO inventory_scrap_record", inventory_scrap)
        self.assertIn("inventory_scrapped", inventory_scrap)
        self.assertIn('self._store_idempotency_result("inventory.scrap"', inventory_scrap)
        # 报废不得回补库存：不允许增加型号或仓库库存，也不允许删除使用记录。
        self.assertNotIn("quantity = quantity +", inventory_scrap)
        self.assertNotIn("DELETE FROM {usage_table}", inventory_scrap)
        self.assertNotIn("inventory_movement_log", inventory_scrap)

    def test_computer_scrap_retires_archives_and_snapshots_the_asset(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        computer_scrap = service.split("    def scrap_computer(", 1)[1].split(
            "\n    def _inventory_scrap_rows(",
            1,
        )[0]

        self.assertIn("START TRANSACTION;", computer_scrap)
        self.assertIn("FOR UPDATE;", computer_scrap)
        self.assertIn("it_asset_status = 'retired'", computer_scrap)
        self.assertIn("is_archived = 1", computer_scrap)
        self.assertIn("archived_at = CURRENT_TIMESTAMP", computer_scrap)
        self.assertIn("assignment_status = 'returned'", computer_scrap)
        self.assertIn("INSERT INTO asset_scrap_record", computer_scrap)
        self.assertIn("'Computer scrap'", computer_scrap)
        self.assertIn("computer_scrapped", computer_scrap)
        self.assertIn('self._store_idempotency_result("computer.scrap"', computer_scrap)
        self.assertNotIn("quantity = quantity +", computer_scrap)
        self.assertNotIn("DELETE FROM computer_asset", computer_scrap)

    def test_archived_computers_leave_the_ledger_but_keep_their_records(self):
        state_reader = (ROOT / "server.py").read_text(encoding="utf-8")
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")

        self.assertIn("AND ca.is_archived = 0", state_reader)
        self.assertIn("AND asset.is_archived = 0", service)
        self.assertIn("'scrap_reason', 'inventory_scrap_record', 'asset_scrap_record'", state_reader)
        self.assertIn("required_table_count = 57", state_reader)

    def test_frontend_exposes_scrap_actions_and_records_page(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-action="open-usage-scrap"', app)
        self.assertIn('data-action="open-computer-scrap"', app)
        self.assertIn('data-action="open-scrap-record"', app)
        self.assertIn('data-action="export-scrap-records"', app)
        self.assertIn('data-action="apply-scrap-filters"', app)
        self.assertIn('hasPermission("scrap_management", "create")', app)
        self.assertIn("function renderScrapRecordsPage()", app)
        self.assertIn("function handleScrapSubmit(form)", app)
        self.assertIn('if (type === "scrap") handleScrapSubmit(form);', app)
        self.assertIn('scrapRecords: "scrap_management"', app)
        self.assertIn('scrap_management: "报废管理"', app)
        self.assertIn('data-page="scrapRecords"', page)
        self.assertIn('"scrapSearch"', app)

    def test_version_notes_document_the_scrap_release(self):
        notes = (ROOT / "VERSION_NOTES.md").read_text(encoding="utf-8")
        release = notes.split("## v2.3.0", 1)

        self.assertEqual(2, len(release), "VERSION_NOTES.md must document v2.3.0")
        body = release[1].split("\n## ", 1)[0]
        self.assertIn("20260915_001_scrap_management.sql", body)
        self.assertIn("报废", body)
        self.assertIn("不回补库存", body)


class UpdateSourceSelectionTests(TestCase):
    """更新按钮内置 GitHub 来源，并提供自定义地址入口。"""

    def test_update_panel_has_builtin_github_and_custom_source(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn(
            'const GITHUB_UPDATE_REPOSITORY_URL = "https://github.com/freeisme/asset-center.git";',
            app,
        )
        self.assertIn("const UPDATE_SOURCES = {", app)
        self.assertIn('github: "GitHub 官方更新"', app)
        self.assertIn('custom: "自定义更新地址"', app)
        self.assertIn("function currentUpdateSource()", app)
        self.assertIn(
            'if (currentUpdateSource() === "github") return GITHUB_UPDATE_REPOSITORY_URL;',
            app,
        )
        self.assertIn('data-update-source', app)
        self.assertIn('data-update-repository-url', app)
        self.assertIn('"从 GitHub 检查更新"', app)
        self.assertIn("updateSource === \"custom\"", app)

    def test_only_custom_source_persists_the_repository_url(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        server_source = (ROOT / "server.py").read_text(encoding="utf-8")

        self.assertIn('persistRepositoryUrl: updateSource === "custom"', app)
        self.assertIn('payload.get("persistRepositoryUrl", True)', server_source)
        self.assertIn("if \"repositoryUrl\" in payload and parse_bool(", server_source)
        self.assertIn("updateCustomRepositoryUrl", app)


class RecoveryInboundTests(TestCase):
    """登记物资回收也必须入库，缺少品牌型号时自动建档并输出记录。"""

    def test_recovery_creates_catalog_entries_and_always_adds_stock(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        offboard = service.split("    def offboard_employee(", 1)[1].split(
            "\n    def _recovery_records_since(",
            1,
        )[0]

        self.assertIn("def _recovery_catalog_sql(", service)
        self.assertIn("INSERT IGNORE INTO it_inventory_brand", service)
        self.assertIn("INSERT IGNORE INTO it_inventory_model", service)
        self.assertIn("未填写品牌", service)
        self.assertIn("未填写型号", service)
        # 登记物资（未扣库存）同样入库，不再以 stock_adjusted 作为入库条件
        self.assertIn("@allocation_recovery_quantity = 0", offboard)
        self.assertIn("AND @recovery_model_id > 0", offboard)
        self.assertNotIn("AND {stock_adjusted} = 1", offboard)
        self.assertIn("'leave_recovery'", offboard)

    def test_single_returns_recover_into_stock_as_well(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        allocation_return = service.split("    def return_inventory(", 1)[1].split(
            "\n    def return_usage_inventory(",
            1,
        )[0]
        legacy_return = service.split("    def return_usage_inventory(", 1)[1].split(
            "\n    def list_allocations(",
            1,
        )[0]

        for source in (allocation_return, legacy_return):
            self.assertIn("_recovery_catalog_sql(", source)
            self.assertIn("@recovery_model_id > 0", source)
            self.assertNotIn("{1 if stock_adjusted else 0} = 1", source)
            self.assertIn("请选择回收目标仓库。", source)

    def test_recovery_records_are_returned_and_shown_in_a_modal(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("def _recovery_records_since(", service)
        self.assertIn("def _offboarding_unrecovered_items(", service)
        self.assertIn('"recoveryRecords"', service)
        self.assertIn('"unrecoveredItems"', service)
        self.assertIn("function showRecoveryResultModal(result = {})", app)
        self.assertIn("回收完成", app)
        self.assertIn("已回收并生成库存记录", app)
        self.assertIn("未回收物资", app)
        self.assertIn("showRecoveryResultModal({", app)
        self.assertIn('if (matches.length) return recoveryRecords;', app)


class OffboardingRecoveryWarehouseTests(TestCase):
    """回收必须显式选择目标仓库，且仓库要落库留痕。"""

    def test_backend_requires_and_records_the_recovery_warehouse(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        normalization = service.split("    def _normalize_offboarding_plan(", 1)[1].split(
            "\n    def offboard_employee(",
            1,
        )[0]
        offboard = service.split("    def offboard_employee(", 1)[1]

        self.assertIn('raise self.api_error("选择回收时必须指定回收目标仓库。")', normalization)
        self.assertIn(
            'raw_item.get("recoveryWarehouseId") or raw_item.get("warehouseId")',
            normalization,
        )
        self.assertIn('{"warehouseId": requested_warehouse_id}', normalization)
        self.assertIn('"employees",', normalization)
        self.assertIn("require_explicit=True", normalization)
        # 目标仓库对所有回收项生效，不再以“是否扣减过库存”为条件。
        self.assertNotIn("and stock_adjusted:\n                    source_warehouse_ids", normalization)
        self.assertIn("THEN {recovery_warehouse_id_sql}", offboard)
        self.assertIn('{recovery_warehouse_id_sql if action == "recover" else "NULL"}', offboard)

    def test_frontend_requires_an_explicit_warehouse_without_preselecting_one(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("const requiresRecoveryWarehouse = action === \"recover\";", app)
        self.assertIn("回收目标仓库 *", app)
        self.assertIn(
            'warehouseOptions("", "请选择回收目标仓库", currentUserOrgId(), false)',
            app,
        )
        self.assertIn('return showToast("选择回收时必须指定回收目标仓库。", true);', app)
        self.assertIn(
            'function warehouseOptions(selectedId = "", placeholder = "请选择仓库", '
            'preferredOrgId = "", useDefaultSelection = true)',
            app,
        )
        self.assertIn(
            "useDefaultSelection && preferredOrgId ? defaultWarehouseIdForOrg(preferredOrgId) : \"\"",
            app,
        )
        self.assertNotIn('action === "recover" && row.dataset.stockAdjusted === "1"', app)


class WarehouseInventoryRegressionTests(TestCase):
    def test_warehouse_migration_is_incremental_and_preserves_legacy_history(self):
        migration = (
            ROOT / "database" / "migrations" / "20260902_001_inventory_warehouses.sql"
        ).read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_warehouse", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_warehouse_stock", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS inventory_transfer_log", migration)
        self.assertIn("information_schema.columns", migration)
        self.assertIn("information_schema.table_constraints", migration)
        self.assertIn("INSERT INTO inventory_warehouse", migration)
        self.assertIn("VALUES ('WH-001', '仓库1'", migration)
        self.assertIn("SELECT @default_warehouse_id, model_id, quantity", migration)
        self.assertIn("warehouse_management", migration)
        self.assertNotIn("DROP TABLE", migration.upper())
        self.assertNotIn("DELETE FROM inventory_movement_log", migration)

        transfer_table = migration.split(
            "CREATE TABLE IF NOT EXISTS inventory_transfer_log",
            1,
        )[1].split("\n\nSET @has_allocation_warehouse", 1)[0]
        self.assertIn(
            "ON DELETE RESTRICT,\n"
            "  CONSTRAINT fk_inventory_transfer_target",
            transfer_table,
        )
        self.assertNotIn(
            "source_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)\n"
            "    ON DELETE RESTRICT ON UPDATE CASCADE",
            transfer_table,
        )
        self.assertNotIn(
            "target_warehouse_id) REFERENCES inventory_warehouse (warehouse_id)\n"
            "    ON DELETE RESTRICT ON UPDATE CASCADE",
            transfer_table,
        )

        bootstrap = (
            ROOT / "database" / "bootstrap" / "01_schema.sql"
        ).read_text(encoding="utf-8")
        bootstrap_transfer_table = bootstrap.split(
            "CREATE TABLE inventory_transfer_log",
            1,
        )[1].split("\n\nCREATE TABLE inventory_movement_log", 1)[0]
        self.assertNotIn(
            "warehouse_id)\n    ON DELETE RESTRICT ON UPDATE CASCADE",
            bootstrap_transfer_table,
        )

    def test_warehouse_routes_require_permissions_and_use_command_endpoint(self):
        router = (ROOT / "office_asset" / "api_router.py").read_text(encoding="utf-8")
        server_source = (ROOT / "server.py").read_text(encoding="utf-8")

        self.assertIn('path == "/api/inventory/warehouses" and method == "GET"', router)
        self.assertIn('path == "/api/inventory/warehouses" and method == "POST"', router)
        self.assertIn('len(parts) == 5 and method == "DELETE"', router)
        self.assertIn('self._write_context(handler, "warehouse_management", "create")', router)
        self.assertIn('self._write_context(handler, "warehouse_management", "update")', router)
        self.assertIn('self._write_context(handler, "warehouse_management", "delete")', router)
        self.assertIn('path == "/api/inventory/transfers" and method == "POST"', router)
        self.assertIn('self._inventory_write_context(handler, "update")', router)
        self.assertIn('self.deps.require_permission(context, "warehouse_management", "create")', router)
        self.assertIn('self.assets.transfer_inventory(', router)
        delete_handler = server_source.split("    def do_DELETE(self) -> None:", 1)[1].split(
            "\n    def end_headers",
            1,
        )[0]
        self.assertIn('if self.path.startswith("/api/"):', delete_handler)
        self.assertIn("self.handle_api()", delete_handler)
        self.assertIn('"code": "STATE_CONFLICT"', delete_handler)

    def test_warehouse_service_is_scoped_transactional_and_idempotent(self):
        service = (ROOT / "office_asset" / "asset_service.py").read_text(encoding="utf-8")
        transfer = service.split("    def transfer_inventory(", 1)[1].split(
            "\n    def return_inventory(",
            1,
        )[0]
        delete = service.split("    def delete_warehouse(", 1)[1].split(
            "\n    def list_warehouse_stock(",
            1,
        )[0]

        self.assertIn("def _assert_warehouse_access(", service)
        self.assertIn('module_code: str = "warehouse_management"', service)
        self.assertIn("self.scope.assert_org_access(context, warehouse.get(\"orgId\"))", service)
        self.assertIn('self._idempotency_result("inventory.transfer"', transfer)
        self.assertIn("START TRANSACTION;", transfer)
        self.assertIn("first_warehouse_id, second_warehouse_id = sorted(", transfer)
        self.assertIn("FOR UPDATE;", transfer)
        self.assertIn("UPDATE inventory_warehouse_stock", transfer)
        self.assertIn("INSERT INTO inventory_transfer_log", transfer)
        self.assertIn("inventory_transfer", transfer)
        self.assertIn('self._store_idempotency_result("inventory.transfer"', transfer)
        self.assertIn('warehouse.get("code")) == "WH-001"', delete)
        self.assertIn("默认仓库“仓库1”不能删除", delete)
        self.assertIn("inventory_transfer_log", delete)

    def test_warehouse_state_filtering_and_frontend_controls_are_scoped(self):
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        state_reader = (ROOT / "server.py").read_text(encoding="utf-8")

        self.assertIn('for module_code in ("it_assets", "employees", "organizations", "warehouse_management")', state_reader)
        self.assertIn('if can_view("warehouse_management"):', state_reader)
        self.assertIn('result["warehouseStocks"] = [', state_reader)
        self.assertIn('text_value(item.get("warehouseId")) in visible_warehouse_ids', state_reader)
        self.assertIn('class="inventory-warehouse-tabs"', app)
        self.assertIn('data-action="select-inventory-warehouse"', app)
        self.assertIn('data-action="open-warehouse-directory"', app)
        self.assertIn('data-action="open-inventory-transfer"', app)
        self.assertIn('warehouseSelectField("入库仓库", "warehouseId"', app)
        self.assertIn('warehouseSelectField(', app)
        self.assertIn('"回收目标仓库"', app)
        self.assertIn('selectField("调出仓库", "sourceWarehouseId"', app)
        self.assertIn('selectField("调入仓库", "targetWarehouseId"', app)
        self.assertIn("class=\"readonly-label\">当前仓库</span>", app)
        self.assertNotIn("<label>当前仓库</label>", app)


if __name__ == "__main__":
    import unittest

    unittest.main()
