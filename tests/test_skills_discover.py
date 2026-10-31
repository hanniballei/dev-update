import contextlib
import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import skills_discover


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class FakeGitHub:
    def __init__(self, repos, failures=None):
        self.repos = repos
        self.failures = failures or {}
        self.requests = []
        self.authorizations = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.requests.append(url)
        self.authorizations.append(request.get_header("Authorization"))
        rest = url.split("/repos/", 1)[1]
        if "/git/trees/" in rest:
            source = rest.split("/git/trees/", 1)[0]
            kind = "tree"
        else:
            source = rest
            kind = "repo"
        failure = self.failures.get(source)
        if failure == "rate_limit":
            headers = Message()
            headers["x-ratelimit-remaining"] = "0"
            raise HTTPError(url, 403, "Forbidden", headers, None)
        if failure == 404:
            raise HTTPError(url, 404, "Not Found", Message(), None)
        if failure == "network":
            raise URLError("connection refused")
        info = self.repos[source]
        if kind == "repo":
            return FakeResponse({"default_branch": info["branch"]})
        tree = [{"type": "blob", "path": path} for path in info["paths"]]
        return FakeResponse({"tree": tree, "truncated": info.get("truncated", False)})


def github_source(name, path, source="owner/repo"):
    return {"source": source, "sourceType": "github", "skillPath": path}


class SkillsDiscoverTests(unittest.TestCase):
    def invoke(self, lock_data, fake, *arguments, env=None):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / ".skill-lock.json"
            lock_path.write_text(json.dumps(lock_data), encoding="utf-8")
            output = io.StringIO()
            clean_env = {"GITHUB_TOKEN": "", "GH_TOKEN": ""}
            clean_env.update(env or {})
            with (
                patch.object(skills_discover.urllib.request, "urlopen", side_effect=fake),
                patch.object(skills_discover.subprocess, "run", side_effect=OSError("no gh")),
                patch.dict(skills_discover.os.environ, clean_env),
                contextlib.redirect_stdout(output),
            ):
                exit_code = skills_discover.main(["--lock", str(lock_path), *arguments])
        return exit_code, json.loads(output.getvalue())

    def test_untracked_and_missing_are_reported(self):
        lock = {
            "skills": {
                "a": github_source("a", "skills/a/SKILL.md"),
                "old": github_source("old", "skills/old/SKILL.md"),
            }
        }
        paths = ["skills/a/SKILL.md", "skills/new/SKILL.md"]
        fake = FakeGitHub({"owner/repo": {"branch": "main", "paths": paths}})

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["sources_checked"], 1)
        self.assertEqual(
            report["untracked"],
            [
                {
                    "source": "owner/repo",
                    "group": "skills",
                    "name": "new",
                    "path": "skills/new/SKILL.md",
                }
            ],
        )
        self.assertEqual(
            report["missing_upstream"],
            [
                {
                    "source": "owner/repo",
                    "group": "skills",
                    "name": "old",
                    "path": "skills/old/SKILL.md",
                    "installed_name": "old",
                }
            ],
        )
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["rate_limited"])
        self.assertFalse(report["token_used"])

    def test_no_diff_produces_empty_lists(self):
        lock = {"skills": {"a": github_source("a", "skills/a/SKILL.md")}}
        fake = FakeGitHub({"owner/repo": {"branch": "main", "paths": ["skills/a/SKILL.md"]}})

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["untracked"], [])
        self.assertEqual(report["missing_upstream"], [])

    def test_dot_directories_are_kept_when_comparing_paths(self):
        lock = {
            "skills": {
                "claude": github_source("claude", ".claude/skills/claude/SKILL.md"),
                "agents": github_source("agents", "./.agents/skills/agents/SKILL.md"),
            }
        }
        paths = [".claude/skills/claude/SKILL.md", ".agents/skills/agents/SKILL.md"]
        fake = FakeGitHub({"owner/repo": {"branch": "main", "paths": paths}})

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["untracked"], [])
        self.assertEqual(report["missing_upstream"], [])

    def test_rate_limit_stops_remaining_sources(self):
        lock = {
            "skills": {
                "a": github_source("a", "skills/a/SKILL.md", "owner/aaa"),
                "b": github_source("b", "skills/b/SKILL.md", "owner/bbb"),
            }
        }
        fake = FakeGitHub(
            {
                "owner/aaa": {"branch": "main", "paths": []},
                "owner/bbb": {"branch": "main", "paths": []},
            },
            failures={"owner/aaa": "rate_limit"},
        )

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertTrue(report["rate_limited"])
        self.assertEqual(report["sources_checked"], 0)
        self.assertEqual(
            report["errors"],
            [
                {"source": "owner/aaa", "error": "rate_limited"},
                {"source": "owner/bbb", "error": "skipped_after_rate_limit"},
            ],
        )

    def test_repository_not_found_does_not_stop_other_sources(self):
        lock = {
            "skills": {
                "a": github_source("a", "skills/a/SKILL.md", "owner/aaa"),
                "b": github_source("b", "skills/b/SKILL.md", "owner/bbb"),
            }
        }
        fake = FakeGitHub(
            {"owner/bbb": {"branch": "main", "paths": ["skills/new/SKILL.md"]}},
            failures={"owner/aaa": 404},
        )

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["sources_checked"], 1)
        self.assertEqual(
            report["errors"], [{"source": "owner/aaa", "error": "repository_not_found"}]
        )
        self.assertEqual(len(report["untracked"]), 1)

    def test_unsupported_source_type_is_listed_not_checked(self):
        lock = {
            "skills": {
                "a": github_source("a", "skills/a/SKILL.md"),
                "local": {
                    "source": "/opt/skills",
                    "sourceType": "local",
                    "skillPath": "local/SKILL.md",
                },
            }
        }
        fake = FakeGitHub({"owner/repo": {"branch": "main", "paths": ["skills/a/SKILL.md"]}})

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["sources_checked"], 1)
        self.assertEqual(
            report["unsupported_sources"],
            [{"source": "/opt/skills", "sourceType": "local", "skills": ["local"]}],
        )

    def test_source_filter_selects_subset_and_rejects_unknown(self):
        lock = {
            "skills": {
                "a": github_source("a", "skills/a/SKILL.md", "owner/aaa"),
                "b": github_source("b", "skills/b/SKILL.md", "owner/bbb"),
            }
        }
        fake = FakeGitHub(
            {
                "owner/aaa": {"branch": "main", "paths": ["skills/a/SKILL.md"]},
                "owner/bbb": {"branch": "main", "paths": []},
            }
        )

        exit_code, report = self.invoke(lock, fake, "--source", "owner/bbb")

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["sources_checked"], 1)
        self.assertTrue(all("/owner/bbb" in url for url in fake.requests))

        exit_code, report = self.invoke(lock, fake, "--source", "owner/unknown")
        self.assertEqual(exit_code, 1)
        self.assertIn("owner/unknown", report["error"])

    def test_truncated_tree_is_flagged(self):
        lock = {"skills": {"a": github_source("a", "skills/a/SKILL.md")}}
        fake = FakeGitHub(
            {
                "owner/repo": {
                    "branch": "main",
                    "paths": ["skills/a/SKILL.md"],
                    "truncated": True,
                }
            }
        )

        exit_code, report = self.invoke(lock, fake)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["truncated_sources"], ["owner/repo"])

    def test_token_from_environment_is_sent(self):
        lock = {"skills": {"a": github_source("a", "skills/a/SKILL.md")}}
        fake = FakeGitHub({"owner/repo": {"branch": "main", "paths": ["skills/a/SKILL.md"]}})

        exit_code, report = self.invoke(lock, fake, env={"GITHUB_TOKEN": "secret-token"})

        self.assertEqual(exit_code, 0)
        self.assertTrue(report["token_used"])
        self.assertEqual(set(fake.authorizations), {"Bearer secret-token"})

    def test_missing_lock_is_fatal(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = skills_discover.main(["--lock", "/nonexistent/.skill-lock.json"])
        report = json.loads(output.getvalue())

        self.assertEqual(exit_code, 1)
        self.assertIn("Cannot read skill lock", report["error"])

    def test_describe_path_handles_root_and_nested_skills(self):
        root = skills_discover.describe_path("owner/repo", "SKILL.md")
        expected = {"source": "owner/repo", "group": "(root)", "name": "repo", "path": "SKILL.md"}
        self.assertEqual(root, expected)
        nested = skills_discover.describe_path("owner/repo", "skills/engineering/pr/SKILL.md")
        self.assertEqual(nested["group"], "skills/engineering")
        self.assertEqual(nested["name"], "pr")

    def test_default_lock_path_prefers_xdg_state_home(self):
        path = skills_discover.default_lock_path({"XDG_STATE_HOME": "/tmp/xdg"})
        self.assertEqual(path, Path("/tmp/xdg/skills/.skill-lock.json"))
        path = skills_discover.default_lock_path({})
        self.assertEqual(path, Path.home() / ".agents" / ".skill-lock.json")


if __name__ == "__main__":
    unittest.main()
