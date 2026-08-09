# registry-publish-race-e2e

Purpose-built **registry-concurrency** certification lane for `zed-pkg-test`.

Certify concurrent package publication, immutable checksums, and atomic tag movement.

## Contract

- Canonical repository: `zed-pkg-test/registry-publish-race-e2e`
- Visibility: `public`
- Default branch: `main`
- Tracking: `DEN-3286`
- Fleet manifest: `5d1cf8cb7af82a81660bf2fe7536759c7b15bd01bef4a4a04730095ad998d056`

This repository is deliberately small. It provides an independently versioned
home for destructive, long-running, adversarial, or cross-version test fixtures
without coupling their lifecycle to production source repositories.

## Verify the bootstrap contract

```sh
python3 scripts/verify.py
python3 -m unittest discover -s tests -v
```

Product-specific fixtures should be added incrementally through reviewed pull
requests. Do not place production credentials or customer data in this test lane.
