# Official WMQL Queries

Unmodified resources from `demianw/tract_querier` commit
`5c69c594d489859e08485110678dca7f6f4cba40` (upstream master checked 2026-10-24).

| Resource | SHA256 |
| --- | --- |
| `freesurfer_queries.qry` | `554a4eed4b99cdbe497cc5296d49ea8a65961e2b1920c1868e41d2f0dfc080ba` |
| `FreeSurfer.qry` | `3fc2f3685af5061f5106f5f3c6c5644b926f0850211de0380082f274cb7be8a0` |

The rules declare 48 output queries; bilateral `.side` definitions expand to
left/right. This is not a guarantee of 48 nonempty bundles or a partition of all
input streamlines. Intermediate `|=` definitions are not output bundles.

The adjacent `LICENSE.txt` is copied from the upstream `license.rst`. Execution
uses the installed author Tract Querier, not a reimplementation of its rules.
DDParcel labels are checked without substituting or relaxing these definitions.
