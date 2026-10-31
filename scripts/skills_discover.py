#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "dev-update-skills-discover"
API_BASE = "https://api.github.com"


class DiscoverError(Exception):
    pass


def default_lock_path(env=os.environ):
    xdg_state = env.get("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state) / "skills" / ".skill-lock.json"
    return Path.home() / ".agents" / ".skill-lock.json"


def load_lock(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise DiscoverError(f"Cannot read skill lock {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise DiscoverError(f"Skill lock {path} is not valid JSON: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("skills"), dict):
        raise DiscoverError(f"Skill lock {path} has no 'skills' object")
    return data


def strip_relative_prefix(path):
    """Drop a leading './' or '/' without eating dot-directories like '.claude'."""
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def group_sources(lock):
    github = {}
    unsupported = {}
    for name, meta in lock["skills"].items():
        if not isinstance(meta, dict):
            continue
        source = meta.get("source")
        skill_path = meta.get("skillPath")
        if not isinstance(source, str) or not isinstance(skill_path, str):
            continue
        entry = {"name": name, "path": strip_relative_prefix(skill_path)}
        if meta.get("sourceType") == "github":
            github.setdefault(source, []).append(entry)
        else:
            unsupported.setdefault(source, {"sourceType": meta.get("sourceType"), "skills": []})[
                "skills"
            ].append(name)
    return github, unsupported


def resolve_token(arguments, env=os.environ):
    if arguments.token:
        return arguments.token
    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        if env.get(variable):
            return env[variable]
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


def github_get(url, token, timeout):
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        remaining = error.headers.get("x-ratelimit-remaining") if error.headers else None
        if error.code == 403 and remaining == "0":
            raise DiscoverError("rate_limited") from error
        if error.code == 404:
            raise DiscoverError("repository_not_found") from error
        raise DiscoverError(f"HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise DiscoverError(f"{type(error).__name__}: {error}") from error


def upstream_skill_paths(source, token, timeout):
    repo = github_get(f"{API_BASE}/repos/{source}", token, timeout)
    branch = repo.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise DiscoverError("default branch unknown")
    tree = github_get(f"{API_BASE}/repos/{source}/git/trees/{branch}?recursive=1", token, timeout)
    entries = tree.get("tree")
    if not isinstance(entries, list):
        raise DiscoverError("tree response invalid")
    paths = {
        entry["path"]
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and isinstance(entry.get("path"), str)
        and entry["path"].lower().endswith("skill.md")
    }
    return paths, bool(tree.get("truncated"))


def describe_path(source, path):
    parent, separator, _ = path.rpartition("/")
    name = parent.rpartition("/")[2] if separator else source.rpartition("/")[2]
    group = parent.rpartition("/")[0] if "/" in parent else "(root)"
    return {"source": source, "group": group or "(root)", "name": name, "path": path}


def discover(sources, token, timeout):
    report = {
        "sources_checked": 0,
        "untracked": [],
        "missing_upstream": [],
        "errors": [],
        "truncated_sources": [],
        "rate_limited": False,
    }
    rate_limited = False
    for source in sorted(sources):
        if rate_limited:
            report["errors"].append({"source": source, "error": "skipped_after_rate_limit"})
            continue
        tracked = {entry["path"]: entry["name"] for entry in sources[source]}
        try:
            upstream, truncated = upstream_skill_paths(source, token, timeout)
        except DiscoverError as error:
            if str(error) == "rate_limited":
                rate_limited = True
                report["rate_limited"] = True
            report["errors"].append({"source": source, "error": str(error)})
            continue
        report["sources_checked"] += 1
        if truncated:
            report["truncated_sources"].append(source)
        for path in sorted(upstream - tracked.keys()):
            report["untracked"].append(describe_path(source, path))
        for path in sorted(set(tracked) - upstream):
            report["missing_upstream"].append(
                {**describe_path(source, path), "installed_name": tracked[path]}
            )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Read-only: diff tracked skills in the global skill lock against upstream "
            "GitHub sources. Never writes to the lock or disk. Output is JSON."
        )
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Limit to this lock source (e.g. owner/repo); repeatable",
    )
    parser.add_argument("--lock", help="Skill lock path (default: CLI resolution order)")
    parser.add_argument("--token", help="GitHub token (default: GITHUB_TOKEN/GH_TOKEN/gh auth)")
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="Per-request timeout in seconds"
    )
    arguments = parser.parse_args(argv)
    try:
        lock_path = Path(arguments.lock) if arguments.lock else default_lock_path()
        lock = load_lock(lock_path)
        github, unsupported = group_sources(lock)
        unknown = set(arguments.source) - github.keys()
        if unknown:
            raise DiscoverError(f"Sources not in lock: {', '.join(sorted(unknown))}")
        selected = {key: github[key] for key in arguments.source} if arguments.source else github
        token = resolve_token(arguments)
        report = discover(selected, token, arguments.timeout)
        report["lock"] = str(lock_path)
        report["token_used"] = bool(token)
        report["unsupported_sources"] = [
            {"source": source, **details} for source, details in sorted(unsupported.items())
        ]
        exit_code = 0
    except DiscoverError as error:
        report = {"error": str(error)}
        exit_code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
