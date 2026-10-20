<div align="center">

# Project Website

**Static public assets, separate from private software documentation**

[Project](../../README.md) | [Website](https://chengjinlii.github.io/SlicerDDSurfer/) | [Original Notes](UPSTREAM_README.md) | [中文](README.zh-CN.md)

</div>

---

## Source And Attribution

The website was contributed by [xiaji](https://github.com/xiaji), whose original
Git author is `x1aji <jwjwei@gmail.com>`. Its three original commits
`935a5d9`, `444d8db` and `5b09bc2` are retained as ancestors of `main` through a
normal merge, not a squash, rebase or copied replacement commit. Their author,
committer, timestamps and co-author trailers are unchanged.

Public HTML, styles, scripts, fonts, images, subtitles and the 41,070,370-byte
promo film live under `docs/site/`. Integration moves the original files without
redesigning the site or re-encoding its media. [FACTS.md](FACTS.md),
[SPEC.md](SPEC.md) and [UPSTREAM_README.md](UPSTREAM_README.md) preserve the
contributor's historical source, design and review records. They are not current
installation instructions and are not part of the public deployment.

---

## Publishing

The `Website` workflow validates the site and publishes **only `docs/site/`**
from `main`. It does not publish the repository root or the rest of `docs/`,
which contains internal scientific and release records. Website files are also
excluded from the Slicer extension's runtime package.

The film stays in ordinary Git for static playback. The repository size audit
permits only this exact public path, byte count and SHA256, not arbitrary large
videos or model files. Any replacement needs a separately reviewed update.

The repository owner must first open
[Settings > Pages](https://github.com/ChengjinLii/SlicerDDSurfer/settings/pages)
and set **Source: GitHub Actions**. Publishing from a private repository needs
an eligible paid plan. The website is public; the source repository stays private.
The current connector can read/write repository content but does not expose the
Pages administration endpoint. A successful merge is not proof that Pages is enabled.

If Pages is off or still configured for branch-based publishing, validation
continues, but the deployment job is explicitly skipped with a setup notice.
After enabling Actions, rerun `Website` from the Actions page, or push a site
change. A deployment is accepted only after the deploy job succeeds and the
public URL responds successfully.

Expected URL: `https://chengjinlii.github.io/SlicerDDSurfer/`. The canonical URL,
share tags and 404 home link assume this address. Review the original notes
before changing it. Do not configure `main /docs`: that would expose documents
outside the intended public website.

---

## Local Checks

```bash
python scripts/audit_pages_site.py
python -I Testing/Website/check_site.py
npm ci --prefix Testing/Website
node Testing/Website/browser_check.mjs
```

The browser test uses installed Google Chrome by default. `CHROME_EXECUTABLE`
can point to a compatible Chrome for Testing binary. Optional `PLAYWRIGHT_CORE`
selects an existing module; otherwise the pinned local dependency is used.
Video codec/playback checks are still required. Optional ffprobe checks clearly
report SKIP when ffprobe is unavailable.

Screenshots and browser results stay under ignored `Testing/Website/out/`.
Browser dependencies are test-only and do not ship in the website or Slicer
extension. The public-file allowlist rejects private documents and symlinks.

---

## Evidence Boundaries

The page describes the demonstrated workflow and its reviewed evidence, not a
guarantee that every scientific route passes on every subject or platform.
Keep its release-state and review caveats until stronger evidence exists.
The film's automatic transcript/timing checks do not replace listening to its
audio mix; the contributor recorded that human audio review is still pending.
