import contextlib
import copy
import io
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts import npm_update


class FakeNpm:
    def __init__(self, installed=None, latest=None, failures=None):
        self.installed = copy.deepcopy(installed or {})
        self.latest = latest or {}
        self.failures = failures or set()
        self.calls = []

    def __call__(self, command, **options):
        self.calls.append(command)
        operation = command[1]
        if operation == "prefix":
            output = "/tmp/test-node\n"
            exit_code = 0
        elif operation == "ls":
            output = json.dumps({"dependencies": self.installed})
            exit_code = 0
        elif operation == "outdated":
            entries = {
                name: {"current": self.installed[name]["version"], "latest": version}
                for name, version in self.latest.items()
                if self.installed[name]["version"] != version
            }
            output = json.dumps(entries)
            exit_code = int(bool(entries))
        elif operation == "install":
            name, separator, version = command[-1].rpartition("@")
            if name in self.failures:
                return subprocess.CompletedProcess(command, 1, "", "private-token-value")
            self.installed[name]["version"] = version
            output = "Installed"
            exit_code = 0
        else:
            raise AssertionError(f"Unexpected operation: {operation}")
        return subprocess.CompletedProcess(command, exit_code, output, "")


class NpmUpdateTests(unittest.TestCase):
    def invoke(self, fake, *arguments):
        output = io.StringIO()
        with (
            patch.object(npm_update.shutil, "which", return_value="/tmp/test-node/bin/npm"),
            patch.object(npm_update.subprocess, "run", side_effect=fake),
            contextlib.redirect_stdout(output),
        ):
            exit_code = npm_update.main(list(arguments))
        return exit_code, json.loads(output.getvalue())

    def test_check_lists_updates_without_installing(self):
        fake = FakeNpm({"tool": {"version": "1.0.0"}}, {"tool": "2.0.0"})
        exit_code, report = self.invoke(fake)
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["prefix"], "/tmp/test-node")
        self.assertEqual(report["mode"], "check")
        self.assertTrue(report["updates"][0]["major_upgrade"])
        self.assertEqual([command[1] for command in fake.calls], ["prefix", "ls", "outdated"])

    def test_current_inventory_includes_codex_without_installing(self):
        fake = FakeNpm({"@openai/codex": {"version": "0.160.1"}})
        exit_code, report = self.invoke(fake)
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["codex_installed"], "0.160.1")
        self.assertEqual(report["updates"], [])

    def test_apply_updates_exact_versions_and_npm_last(self):
        fake = FakeNpm(
            {
                "npm": {"version": "10.0.0"},
                "@openai/codex": {"version": "0.159.0"},
                "z-tool": {"version": "1.0.0"},
            },
            {"npm": "11.0.0", "@openai/codex": "0.160.1", "z-tool": "2.0.0"},
        )
        exit_code, report = self.invoke(fake, "--apply")
        self.assertEqual(exit_code, 0)
        installs = [command for command in fake.calls if command[1] == "install"]
        self.assertEqual(
            [command[-1] for command in installs],
            ["@openai/codex@0.160.1", "z-tool@2.0.0", "npm@11.0.0"],
        )
        self.assertTrue(all("--global" in command and "--" in command for command in installs))
        self.assertEqual([result["status"] for result in report["results"]], ["verified"] * 3)
        self.assertEqual(report["remaining_updates"], [])
        self.assertEqual(report["results"][0]["after"], "0.160.1")

    def test_selected_package_does_not_update_others(self):
        fake = FakeNpm(
            {"tool": {"version": "1.0.0"}, "other": {"version": "1.0.0"}},
            {"tool": "2.0.0", "other": "2.0.0"},
        )
        exit_code, report = self.invoke(fake, "--apply", "--package", "tool")
        self.assertEqual(exit_code, 0)
        self.assertEqual(fake.installed["other"]["version"], "1.0.0")
        self.assertEqual(len(report["results"]), 1)

    def test_unknown_selected_package_fails_without_install(self):
        fake = FakeNpm({"tool": {"version": "1.0.0"}})
        exit_code, report = self.invoke(fake, "--apply", "--package", "missing")
        self.assertEqual(exit_code, 1)
        self.assertIn("not globally installed", report["error"])
        self.assertNotIn("install", [command[1] for command in fake.calls])

    def test_failed_install_continues_independent_packages_and_returns_failure(self):
        fake = FakeNpm(
            {"a-tool": {"version": "1.0.0"}, "b-tool": {"version": "1.0.0"}},
            {"a-tool": "2.0.0", "b-tool": "2.0.0"},
            failures={"a-tool"},
        )
        exit_code, report = self.invoke(fake, "--apply")
        self.assertEqual(exit_code, 1)
        self.assertEqual([result["status"] for result in report["results"]], ["failed", "verified"])
        self.assertEqual(report["remaining_updates"][0]["package"], "a-tool")
        self.assertNotIn("private-token-value", json.dumps(report))

    def test_successful_install_without_version_change_fails_verification(self):
        fake = FakeNpm({"tool": {"version": "1.0.0"}}, {"tool": "2.0.0"})

        def unchanged_install(command, **options):
            if command[1] == "install":
                fake.calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")
            return fake(command, **options)

        exit_code, report = self.invoke(unchanged_install, "--apply")
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["results"][0]["status"], "failed")
        self.assertEqual(report["results"][0]["after"], "1.0.0")

    def test_verification_failure_preserves_completed_install_results(self):
        fake = FakeNpm({"tool": {"version": "1.0.0"}}, {"tool": "2.0.0"})

        def fail_second_inventory(command, **options):
            if command[1] == "ls" and any(call[1] == "install" for call in fake.calls):
                return subprocess.CompletedProcess(command, 2, "", "")
            return fake(command, **options)

        exit_code, report = self.invoke(fail_second_inventory, "--apply")
        self.assertEqual(exit_code, 1)
        self.assertIn("verification_error", report)
        self.assertEqual(report["results"][0]["status"], "installed")

    def test_empty_inventory_is_valid(self):
        exit_code, report = self.invoke(FakeNpm())
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["installed_count"], 0)
        self.assertIsNone(report["codex_installed"])

    def test_missing_npm_returns_json_error(self):
        output = io.StringIO()
        with (
            patch.object(npm_update.shutil, "which", return_value=None),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(npm_update.main([]), 1)
        self.assertIn("not found", json.loads(output.getvalue())["error"])

    def test_invalid_package_argument_fails_before_commands(self):
        fake = FakeNpm()
        exit_code, report = self.invoke(fake, "--apply", "--package=--unsafe")
        self.assertEqual(exit_code, 1)
        self.assertEqual(fake.calls, [])
        self.assertIn("Invalid", report["error"])

    def test_requested_npm_executable_is_resolved(self):
        with patch.object(npm_update.shutil, "which", return_value=None) as resolve:
            with contextlib.redirect_stdout(io.StringIO()):
                npm_update.main(["--npm", "/another/node/bin/npm"])
        resolve.assert_called_once_with("/another/node/bin/npm")

    def test_read_json_handles_outdated_exit_one(self):
        result = subprocess.CompletedProcess([], 1, '{"tool": {"latest": "2.0.0"}}', "")
        with patch.object(npm_update.subprocess, "run", return_value=result):
            self.assertIn("tool", npm_update.outdated("npm"))

    def test_query_errors_are_not_reported_as_current(self):
        cases = [
            (1, "{}"),
            (1, '{"error":{"code":"E401"}}'),
            (0, '{"errors":["failed"]}'),
            (0, "[]"),
            (0, "not-json"),
            (2, "{}"),
        ]
        for exit_code, output in cases:
            with self.subTest(exit_code=exit_code, output=output):
                result = subprocess.CompletedProcess([], exit_code, output, "")
                with patch.object(npm_update.subprocess, "run", return_value=result):
                    with self.assertRaises(npm_update.UpdateError):
                        npm_update.outdated("npm")

    def test_process_failure_has_context_without_private_output(self):
        result = subprocess.CompletedProcess([], 1, "private-token-value", "private-token-value")
        with patch.object(npm_update.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(npm_update.UpdateError, "npm ls exited with 1"):
                npm_update.inventory("npm")

    def test_timeout_and_os_error_have_context(self):
        errors = [subprocess.TimeoutExpired("npm", 180), FileNotFoundError("private-path")]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(npm_update.subprocess, "run", side_effect=error):
                    with self.assertRaisesRegex(npm_update.UpdateError, "npm prefix"):
                        npm_update.run_npm("npm", ["prefix", "--global"])

    def test_semver_order_and_prerelease_numeric_identifiers(self):
        versions = ["1.0.0-alpha", "1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0-rc.1", "1.0.0"]
        self.assertEqual(sorted(reversed(versions), key=npm_update.version_key), versions)
        self.assertLess(npm_update.version_key("2.9.0"), npm_update.version_key("2.10.0"))
        self.assertEqual(npm_update.version_key("1.0.0+build.1"), npm_update.version_key("1.0.0"))

    def test_invalid_versions_are_not_install_targets(self):
        for version in [None, 2, "linked", "git", "latest", "1.0.0;echo secret", "--force"]:
            with self.subTest(version=version):
                self.assertIsNone(npm_update.version_key(version))

    def test_linked_local_git_and_newer_packages_are_skipped(self):
        cases = [
            ({"version": "1.0.0", "link": True}, "2.0.0", "linked_or_non_registry_source"),
            (
                {"version": "1.0.0", "resolved": "file:/local"},
                "2.0.0",
                "linked_or_non_registry_source",
            ),
            (
                {"version": "1.0.0", "resolved": "git+https://example.com/repo"},
                "2.0.0",
                "linked_or_non_registry_source",
            ),
            ({"version": "1.0.0"}, "linked", "non_registry_version"),
            ({"version": "2.0.0"}, "1.0.0", "installed_version_is_newer_than_latest"),
        ]
        for installed, latest, reason in cases:
            with self.subTest(installed=installed, latest=latest):
                fake = FakeNpm({"tool": installed}, {"tool": latest})
                exit_code, report = self.invoke(fake, "--apply")
                self.assertEqual(exit_code, 0)
                self.assertEqual(report["skipped"][0]["reason"], reason)
                self.assertNotIn("install", [command[1] for command in fake.calls])

    def test_prerelease_upgrades_to_stable(self):
        fake = FakeNpm({"tool": {"version": "1.0.0-rc.2"}}, {"tool": "1.0.0"})
        exit_code, report = self.invoke(fake, "--apply")
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["results"][0]["status"], "verified")

    def test_invalid_or_uninstalled_outdated_entries_are_rejected(self):
        installed = {"tool": {"version": "1.0.0"}}
        cases = [
            {"--force": {"current": "1.0.0", "latest": "2.0.0"}},
            {"tool": []},
            {"missing": {"current": "1.0.0", "latest": "2.0.0"}},
        ]
        for updates in cases:
            with self.subTest(updates=updates):
                with self.assertRaises(npm_update.UpdateError):
                    npm_update.make_plan(installed, updates, set())

    def test_inventory_race_is_rejected(self):
        with self.assertRaisesRegex(npm_update.UpdateError, "Inventory changed"):
            npm_update.make_plan(
                {"tool": {"version": "1.0.0"}},
                {"tool": {"current": "1.1.0", "latest": "2.0.0"}},
                set(),
            )

    def test_invalid_inventory_shape_is_rejected(self):
        for dependencies in [[], {"tool": None}]:
            with self.subTest(dependencies=dependencies):
                result = subprocess.CompletedProcess(
                    [], 0, json.dumps({"dependencies": dependencies}), ""
                )
                with patch.object(npm_update.subprocess, "run", return_value=result):
                    with self.assertRaisesRegex(npm_update.UpdateError, "invalid dependencies"):
                        npm_update.inventory("npm")


if __name__ == "__main__":
    unittest.main()
