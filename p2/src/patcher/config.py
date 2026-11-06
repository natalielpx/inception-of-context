"""Load and validate ioc.config.yml from the target project root."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger("ioc.config")

CONFIG_NAME = "ioc.config.yml"

DEFAULT_VALIDATE_CMD = "g++ -fsyntax-only -Wall -Werror -Iinclude src/*.cpp"

DEFAULT_EXCLUDES = [
    "node_modules", ".git", "dist", "build", "venv", ".venv",
    "__pycache__", "qdrant_storage",
]


class ConfigError(Exception):
    pass


class IocConfig(BaseModel):
    validate_cmd: str = Field(default=DEFAULT_VALIDATE_CMD, alias="validate")
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_files: int = Field(default=3, ge=1)
    max_shrink: float = Field(default=0.6, gt=0, lt=1)
    timeout_s: int = Field(default=60, ge=1)
    exclude: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDES))

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("validate_cmd")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("validate command must not be empty")
        return v

    @field_validator("exclude")
    @classmethod
    def _merge_defaults(cls, v: list[str]) -> list[str]:
        # user excludes extend the mandatory ones, never replace them
        return sorted(set(DEFAULT_EXCLUDES) | set(v))


def load_config(target: str | Path) -> IocConfig:
    """Read <target>/ioc.config.yml; missing file -> defaults."""
    path = Path(target) / CONFIG_NAME
    if not path.is_file():
        log.info("no %s in %s -> using defaults", CONFIG_NAME, target)
        cfg = IocConfig()
        log.debug("config: %s", cfg.model_dump())
        return cfg
    log.info("loading %s", path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log.error("invalid YAML in %s", path)
        raise ConfigError(f"{CONFIG_NAME}: invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        log.error("top level of %s is %s, expected mapping", path, type(raw).__name__)
        raise ConfigError(f"{CONFIG_NAME}: top level must be a mapping")
    try:
        cfg = IocConfig.model_validate(raw)
    except ValidationError as e:
        log.error("validation failed for %s (%d error(s))", path, e.error_count())
        raise ConfigError(f"{CONFIG_NAME}: {e}") from e
    log.info("config OK: validate=%r max_attempts=%d max_files=%d",
             cfg.validate_cmd, cfg.max_attempts, cfg.max_files)
    log.debug("config: %s", cfg.model_dump())
    return cfg


# ---------------------------------------------------------------- self-test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)-5s %(name)s | %(message)s")
    target = (Path(__file__).resolve().parent / "../../../target").resolve()
    try:
        cfg = load_config(target)
        log.info("SUCCESS: %s", cfg.model_dump())
    except ConfigError as e:
        log.error("FAILED: %s", e)
        raise SystemExit(1)