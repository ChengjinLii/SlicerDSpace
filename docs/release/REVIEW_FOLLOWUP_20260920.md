# Linux release hardening follow-up

This follows the September 12 local review and the September 19 fixes. It
describes source changes, not a declaration of public release readiness.

## Release helper

- Direct invocation now validates fresh-clone report contents, required
  successful steps, real core assets and a full expected commit SHA.
- Asset basenames must be unique, preventing ambiguous replacement uploads.
- New tags target the tested commit; existing tags are resolved and rejected
  when they point elsewhere.
- Reusing an already public release is rejected before uploading/deleting any
  assets. Promotion of an existing draft is a separate reviewed operation.
- The Actions workflow passes the same immutable SHA to the validator and
  release creator. Maintainer instructions document the required arguments.

## Regression coverage

Tests cover rejection before network access, mismatched evidence, duplicate
asset names, mismatched tag commits and attempted public-release reuse. The
surface loader also has a fast regression guarding its explicit RAS/LPS API
contract, complementing the real Slicer round-trip test run on September 19.

## Remaining acceptance work

- Build with a real Slicer SDK, package with CPack, and install the resulting
  package in a clean Slicer profile. Source staging is already tested but does
  not establish this package contract.
- Commit the source changes, then run fresh-clone core-download evidence and
  remote CI on that exact revision. The last unauthenticated GitHub API check
  returned 404/401, so remote status remains unknown.
- Complete representative anatomical review and scientific comparisons.
  Geometry readability, finite values and reproducibility are useful checks
  but do not establish anatomical accuracy across populations.

No release was published and no repository changes were pushed by this follow-up.
