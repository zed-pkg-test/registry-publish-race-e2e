# Agent instructions for zed-pkg-test/registry-publish-race-e2e

## Scope

This repository owns the `registry-concurrency` test lane described in `test-lane.json`.
Keep fixtures deterministic, bounded, and safe to run outside production.

## Git and conflict policy

- Never force-push, rewrite shared history, or discard either side of a conflict.
- Before resolving a conflict, inspect both parents, the full diff, and relevant
  history with `git log --graph --oneline --decorate --all`.
- Resolve semantically: preserve compatible invariants from both sides, reconcile
  renamed concepts, update tests and documentation together, and explain any
  intentionally superseded behavior in the commit or pull request.
- Never use blanket ours/theirs selection as a substitute for understanding.
- Keep `main` releasable and use reviewed feature branches for changes.

## Security

- Never commit tokens, passwords, private keys, decrypted environment files, or
  customer data.
- Use synthetic fixtures and redact diagnostics.
- Keep generated evidence bounded and free of credentials.
