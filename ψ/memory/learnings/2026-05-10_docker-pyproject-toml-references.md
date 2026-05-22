---
name: "Docker build requires all pyproject.toml referenced files"
description: "Hatchling and other build backends require README.md, LICENSE, and other files referenced in pyproject.toml to be present during pip install. Missing files cause cryptic metadata-generation-failed errors."
type: feedback
---

**Rule:** When building a Python package in Docker, ensure all files referenced by `pyproject.toml` (readme, license, etc.) are copied before `pip install .`.

**Why:** In this session, `docker build` failed because `pyproject.toml` referenced `README.md` for hatchling metadata, but the Dockerfile only copied `pyproject.toml` and `src/`. The error `OSError: Readme file does not exist: README.md` was buried deep in pip's subprocess output.

**How to apply:**
- Before `pip install .` in Dockerfile, copy all files referenced in `[project]` table of `pyproject.toml`:
  ```dockerfile
  COPY pyproject.toml .
  COPY README.md .        # if readme = "README.md"
  COPY LICENSE .          # if license = {file = "LICENSE"}
  COPY src/ src/
  ```
- Test Docker builds as part of CI/merge validation, not just during deployment
- If error says `metadata-generation-failed` during `pip install`, check `pyproject.toml` references first

**Applies to:** Any Python project using hatchling, setuptools, or other PEP 517 build backends in Docker.
