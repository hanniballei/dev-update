#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

PACKAGE_NAME = re.compile(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")


class UpdateError(Exception):
    pass


def version_key(version):
    if not isinstance(version, str):
        return None
    match = VERSION.fullmatch(version)
    if match is None:
        return None
    prerelease = match.group(4)
    identifiers = (
        tuple((0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split("."))
        if prerelease
        else ()
    )
    return (
        tuple(int(match.group(position)) for position in (1, 2, 3)),
        prerelease is None,
        identifiers,
    )


def run_npm(npm, arguments, accepted=(0,), timeout=180):
    command = [npm, *arguments]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpdateError(f"npm {arguments[0]}: {type(error).__name__}") from error
    if result.returncode not in accepted:
        raise UpdateError(f"npm {arguments[0]} exited with {result.returncode}")
    return result


def read_json(npm, arguments, accepted=(0,)):
    result = run_npm(npm, arguments, accepted)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise UpdateError(f"npm {arguments[0]} returned invalid JSON") from error
    if not isinstance(data, dict) or "error" in data or data.get("errors"):
        raise UpdateError(f"npm {arguments[0]} returned an error or unexpected JSON")
    if result.returncode and not data:
        raise UpdateError(f"npm {arguments[0]} failed without update data")
    return data


def inventory(npm):
    data = read_json(npm, ["ls", "--global", "--depth=0", "--json"])
    installed = data.get("dependencies", {})
    if not isinstance(installed, dict) or any(
        not isinstance(details, dict) for details in installed.values()
    ):
        raise UpdateError("npm ls returned invalid dependencies")
    return installed


def outdated(npm):
    return read_json(npm, ["outdated", "--global", "--depth=0", "--json"], accepted=(0, 1))


def make_plan(installed, updates, packages):
    unknown = packages - installed.keys()
    if unknown:
        raise UpdateError(f"Packages are not globally installed: {', '.join(sorted(unknown))}")
    plan = []
    skipped = []
    for name, details in sorted(updates.items(), key=lambda item: (item[0] == "npm", item[0])):
        if not PACKAGE_NAME.fullmatch(name) or not isinstance(details, dict):
            raise UpdateError("npm outdated returned an invalid package entry")
        if name not in installed:
            raise UpdateError(f"Outdated package is not in the global inventory: {name}")
        if packages and name not in packages:
            continue
        current = installed[name].get("version")
        latest = details.get("latest")
        entry = {"package": name, "current": current, "latest": latest}
        resolved = installed[name].get("resolved", "")
        if not isinstance(resolved, str):
            raise UpdateError(f"Invalid installed source: {name}")
        if installed[name].get("link") or resolved.startswith(("file:", "git:", "git+", "github:")):
            skipped.append({**entry, "reason": "linked_or_non_registry_source"})
            continue
        current_key = version_key(current)
        latest_key = version_key(latest)
        if current_key is None or latest_key is None:
            skipped.append({**entry, "reason": "non_registry_version"})
        elif latest_key < current_key:
            skipped.append({**entry, "reason": "installed_version_is_newer_than_latest"})
        elif latest_key > current_key:
            if details.get("current") != current:
                raise UpdateError(f"Inventory changed during the check: {name}; rerun")
            plan.append(
                {
                    **entry,
                    "major_upgrade": latest_key[0][0] > current_key[0][0],
                }
            )
    return plan, skipped


def check(npm, packages):
    prefix = run_npm(npm, ["prefix", "--global"]).stdout.strip()
    if not os.path.isabs(prefix):
        raise UpdateError("npm prefix did not return an absolute path")
    installed = inventory(npm)
    plan, skipped = make_plan(installed, outdated(npm), packages)
    return {
        "npm": npm,
        "prefix": prefix,
        "installed_count": len(installed),
        "codex_installed": installed.get("@openai/codex", {}).get("version"),
        "updates": plan,
        "skipped": skipped,
    }


def apply(npm, report, packages):
    report["results"] = []
    for entry in report["updates"]:
        specification = f"{entry['package']}@{entry['latest']}"
        try:
            run_npm(
                npm,
                ["install", "--global", "--no-audit", "--no-fund", "--", specification],
                timeout=900,
            )
        except UpdateError as error:
            report["results"].append({**entry, "status": "failed", "error": str(error)})
        else:
            report["results"].append({**entry, "status": "installed"})
    try:
        after = inventory(npm)
        for result in report["results"]:
            actual = after.get(result["package"], {}).get("version")
            result["after"] = actual
            if result["status"] == "installed":
                result["status"] = "verified" if actual == result["latest"] else "failed"
                if result["status"] == "failed":
                    result["error"] = "Installed version does not match the requested target"
        remaining, skipped = make_plan(after, outdated(npm), packages)
        report["remaining_updates"] = remaining
        report["remaining_skipped"] = skipped
    except UpdateError as error:
        report["verification_error"] = str(error)
    return int(
        bool(report.get("verification_error") or report.get("remaining_updates"))
        or any(result["status"] != "verified" for result in report["results"])
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check global npm packages; update only with --apply. Output is JSON."
    )
    parser.add_argument("--apply", action="store_true", help="Install and verify planned updates")
    parser.add_argument(
        "--package", action="append", default=[], help="Limit to this installed package"
    )
    parser.add_argument(
        "--npm", default="npm", help="npm executable for the intended Node installation"
    )
    arguments = parser.parse_args(argv)
    npm = shutil.which(arguments.npm)
    try:
        if npm is None:
            raise UpdateError("npm executable not found")
        packages = set(arguments.package)
        if any(not PACKAGE_NAME.fullmatch(name) for name in packages):
            raise UpdateError("Invalid --package name")
        report = check(npm, packages)
        report["mode"] = "apply" if arguments.apply else "check"
        exit_code = apply(npm, report, packages) if arguments.apply else 0
    except UpdateError as error:
        report = {"error": str(error)}
        exit_code = 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
