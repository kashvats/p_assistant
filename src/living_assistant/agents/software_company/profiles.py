"""
Role profile loader and validator for the Software Company multi-agent hierarchy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import yaml

from living_assistant.agents.software_company.models import RoleProfile

logger = logging.getLogger("living_assistant.software_company.profiles")


class ProfileError(Exception):
    """Base exception for profile loading and validation errors."""
    pass


class ProfileNotFoundError(ProfileError):
    """Raised when a requested role profile is not found."""
    pass


class ProfileValidationError(ProfileError):
    """Raised when a role profile YAML fails schema validation."""
    pass


class ProfileLoader:
    """
    Parses, validates, and caches YAML role profiles from the profiles directory.
    """

    def __init__(self, profiles_dir: Path | str | None = None) -> None:
        if profiles_dir is None:
            self.profiles_dir = Path(__file__).resolve().parent / "profiles"
        else:
            self.profiles_dir = Path(profiles_dir).resolve()

        self._cache: dict[str, RoleProfile] = {}

    def get_profile(self, role_id: str) -> RoleProfile:
        """Retrieve a cached profile or load and cache it."""
        if role_id in self._cache:
            return self._cache[role_id]
        return self.load_profile(role_id)

    def load_profile(self, role_id: str) -> RoleProfile:
        """Load and validate a single role profile by role_id from YAML."""
        candidate_paths = [
            self.profiles_dir / f"{role_id}.yaml",
            self.profiles_dir / f"{role_id}.yml",
        ]
        profile_path = next((p for p in candidate_paths if p.is_file()), None)

        if not profile_path:
            raise ProfileNotFoundError(
                f"Role profile for '{role_id}' not found in '{self.profiles_dir}'. "
                f"Looked for: {[str(p) for p in candidate_paths]}"
            )

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            raise ProfileValidationError(f"Failed to parse YAML from {profile_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ProfileValidationError(f"Profile file {profile_path} does not contain a mapping.")

        profile = self.validate_profile(data, source_path=profile_path)
        self._cache[role_id] = profile
        return profile

    def validate_profile(self, data: dict[str, Any], source_path: Path | None = None) -> RoleProfile:
        """Validate raw dictionary data into a RoleProfile model."""
        required_fields = ["role_id", "name", "description", "tier", "allowed_tools"]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            src = f" from {source_path}" if source_path else ""
            raise ProfileValidationError(f"Role profile{src} is missing required fields: {missing}")

        try:
            profile = RoleProfile(**data)
            return profile
        except Exception as exc:
            src = f" from {source_path}" if source_path else ""
            raise ProfileValidationError(f"Role profile validation failed{src}: {exc}") from exc

    def load_all_profiles(self) -> dict[str, RoleProfile]:
        """Discover, load, and validate all YAML role profiles in the profiles directory."""
        if not self.profiles_dir.is_dir():
            logger.warning("Profiles directory does not exist: %s", self.profiles_dir)
            return {}

        results: dict[str, RoleProfile] = {}
        for entry in self.profiles_dir.glob("*.y*ml"):
            if entry.is_file():
                try:
                    with open(entry, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict) and "role_id" in data:
                        profile = self.validate_profile(data, source_path=entry)
                        self._cache[profile.role_id] = profile
                        results[profile.role_id] = profile
                except Exception as exc:
                    logger.error("Error loading profile from %s: %s", entry, exc)
                    raise

        return results

    def clear_cache(self) -> None:
        """Clear cached role profiles."""
        self._cache.clear()
