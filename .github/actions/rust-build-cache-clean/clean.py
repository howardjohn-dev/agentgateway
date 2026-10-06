#!/usr/bin/env python3

import json
import os
from pathlib import Path
import shutil
import subprocess

removed = 0


def remove(path: Path) -> None:
    global removed
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    removed += 1


def artifact_name(filename: str) -> str:
    return filename.rsplit("-", 1)[0]


def clean_named(directory: Path, keep: set[str]) -> None:
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        if artifact_name(path.name) not in keep:
            remove(path)


def clean_profile(profile: Path, package_names: set[str], target_names: set[str]) -> None:
    if profile.name == "tests":
        for nested in (profile / "target", profile / "trybuild"):
            if nested.is_dir():
                clean_target(nested, package_names, target_names)
        for path in profile.iterdir():
            if path.name not in {"target", "trybuild"}:
                remove(path)
        return

    for path in profile.iterdir():
        if path.name not in {"build", ".fingerprint", "deps"}:
            remove(path)

    clean_named(profile / "build", package_names)
    clean_named(profile / ".fingerprint", package_names)
    clean_named(profile / "deps", target_names)


def clean_target(target: Path, package_names: set[str], target_names: set[str]) -> None:
    if not target.is_dir():
        return
    for path in target.iterdir():
        if path.name in {"CACHEDIR.TAG", ".rustc_info.json", ".rust-cache-state"}:
            continue
        if path.is_dir():
            if (path / "CACHEDIR.TAG").exists() or (path / ".rustc_info.json").exists():
                clean_target(path, package_names, target_names)
            else:
                clean_profile(path, package_names, target_names)
        else:
            remove(path)


def clean_registry(registry: Path, packages: list[dict]) -> None:
    package_versions = {f"{package['name']}-{package['version']}" for package in packages}
    crate_files = {f"{package}.crate" for package in package_versions}

    for root_name, keep in (("cache", crate_files), ("src", package_versions)):
        root = registry / root_name
        if not root.is_dir():
            continue
        for registry_dir in root.iterdir():
            if not registry_dir.is_dir():
                continue
            for path in registry_dir.iterdir():
                if path.name not in keep:
                    remove(path)


def clean_git(cargo_home: Path, packages: list[dict]) -> None:
    checkouts = cargo_home / "git" / "checkouts"
    resolved_checkouts = checkouts.resolve()
    repositories: dict[str, set[str]] = {}
    for package in packages:
        manifest = Path(package["manifest_path"]).resolve()
        try:
            relative = manifest.relative_to(resolved_checkouts)
        except ValueError:
            continue
        if len(relative.parts) >= 2:
            repositories.setdefault(relative.parts[0], set()).add(relative.parts[1])

    if checkouts.is_dir():
        for repository in checkouts.iterdir():
            refs = repositories.get(repository.name)
            if refs is None:
                remove(repository)
            elif repository.is_dir():
                for ref in repository.iterdir():
                    if ref.name not in refs:
                        remove(ref)

    databases = cargo_home / "git" / "db"
    if databases.is_dir():
        for repository in databases.iterdir():
            if repository.name not in repositories:
                remove(repository)


def main() -> None:
    metadata = json.loads(
        subprocess.check_output(
            ["cargo", "metadata", "--all-features", "--format-version", "1"],
            text=True,
        )
    )
    packages = metadata["packages"]
    package_names = {package["name"] for package in packages}
    target_names = {
        name
        for package in packages
        for target in package["targets"]
        if {"lib", "proc-macro"}.intersection(target["kind"])
        for name in (
            target["name"].replace("-", "_"),
            f"lib{target['name'].replace('-', '_')}",
        )
    }

    target = Path(metadata["target_directory"])
    cargo_home = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))
    clean_target(target, package_names, target_names)
    clean_registry(cargo_home / "registry", packages)
    clean_git(cargo_home, packages)
    print(f"Removed {removed} obsolete Rust cache entries.")


if __name__ == "__main__":
    main()
