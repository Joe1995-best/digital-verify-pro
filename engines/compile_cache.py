#!/usr/bin/env python3
"""
compile_cache.py — Incremental build cache for RTL compilation.

Tracks file hashes to detect which source files changed since the last
compilation, allowing incremental (re-)compile decisions.

Usage:
    cache = CompileCache(".compile_cache")
    if cache.is_changed("top.sv"):
        print("top.sv changed, recompile needed")
        cache.update(["top.sv", "sub.sv"])
"""
import os
import json
import hashlib

MANIFEST_FILE = "manifest.json"


class CompileCache:
    """Track file modification hashes for incremental compilation."""

    def __init__(self, cache_dir: str):
        self.cache_dir = os.path.abspath(cache_dir)
        self.manifest_path = os.path.join(self.cache_dir, MANIFEST_FILE)
        self._manifest: dict[str, str] = {}
        self._load()

    def _load(self):
        """Load existing manifest from disk."""
        if os.path.isfile(self.manifest_path):
            try:
                with open(self.manifest_path) as f:
                    self._manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._manifest = {}

    def get_hash(self, filepath: str) -> str:
        """Return MD5 hex digest of a file (empty string if not found)."""
        if not os.path.isfile(filepath):
            return ""
        h = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                chunk = f.read(65536)
                while chunk:
                    h.update(chunk)
                    chunk = f.read(65536)
            return h.hexdigest()
        except OSError:
            return ""

    def is_changed(self, filepath: str) -> bool:
        """Check if a file differs from the cached manifest.

        Returns True if the file is new, modified, or missing from cache.
        """
        current = self.get_hash(filepath)
        cached = self._manifest.get(filepath)
        return current != cached

    def update(self, filepaths: list[str]) -> dict[str, str]:
        """Update the manifest with current hashes for the given files.

        Args:
            filepaths: List of file paths to (re-)hash and store.

        Returns:
            The updated manifest dict.
        """
        os.makedirs(self.cache_dir, exist_ok=True)
        for fp in filepaths:
            self._manifest[fp] = self.get_hash(fp)
        self._save()
        return dict(self._manifest)

    def _save(self):
        """Write manifest to disk."""
        with open(self.manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2, sort_keys=True)

    def clear(self):
        """Clear the entire cache."""
        self._manifest = {}
        self._save()
