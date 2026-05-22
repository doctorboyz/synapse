# Lesson Learned: Test the Product, Not Just the Code

**Date**: 2026-05-07
**Source**: rrr: synapse
**Context**: `synapse` CLI wasn't in PATH — user discovered it immediately, but I'd been testing via `python3 -c` workaround for sessions

## Pattern

When developing a CLI tool, it's easy to verify that the code works by importing and calling functions directly (`python3 -c "from src.main import cli_main; cli_main()"`). This tests the code but not the product. The product is the `synapse` command the user types in their terminal. If that command doesn't exist in PATH, the code is correct but the product is broken.

## Why It Happened

The `pip install -e .` installed into `.venv` instead of the system Python. Since I was testing with `python3 -c` calls, I never noticed the binary wasn't in the user's shell PATH. The user tried `synapse serve` from their own terminal and hit "command not found" immediately.

## How to Apply

- After `pip install -e .`, verify the actual binary: `which synapse && synapse --help`
- Test CLI tools the way users will use them: from the shell, not via Python imports
- If you find yourself writing a workaround to test something, that's a signal that the normal path might be broken
- Consider adding a smoke test: `synapse --help` as part of the test suite

## Tags

cli, deployment, PATH, testing, product-vs-code