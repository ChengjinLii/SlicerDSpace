#!/usr/bin/env python3
"""Static checks for the SlicerDDSurfer project site (SPEC section 7.1).

Run from the branch root:  python3 -I tests/check_site.py [--film PATH]
Python 3 standard library only. ffprobe is optional.
Prints one PASS / FAIL / SKIP line per check. Exit code 1 on any FAIL.
"""
import hashlib
import html
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tokenize
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
INDEX = os.path.join(DOCS, "index.html")
PAGE404 = os.path.join(DOCS, "404.html")
FILM = os.path.join(DOCS, "media", "SlicerDDSurfer_promo_1080p.mp4")
SRT = os.path.join(DOCS, "media", "SlicerDDSurfer.en.srt")
FILM_BYTES = 41070370

REPO = "https://github.com/ChengjinLii/SlicerDDSurfer"
BLOB = REPO + "/blob/main/"
ALLOWED_URLS = {
    REPO,
    REPO + ".git",
    BLOB + "CITATION.cff",
    BLOB + "LICENSE.txt",
    BLOB + "THIRD_PARTY_NOTICES.md",
    BLOB + "docs/setup/QUICKSTART.md",
    BLOB + "docs/setup/SUPPORT_MATRIX.md",
    BLOB + "docs/assets/MODEL_ASSET_TERMS.md",
    BLOB + "docs/architecture/IMPLEMENTATION_PROVENANCE.md",
    "https://doi.org/10.1002/advs.76596",
    "https://doi.org/10.1016/j.neuroimage.2021.117934",
    "https://doi.org/10.1109/TMI.2023.3331691",
    "https://doi.org/10.1162/imag_a_00060",
    "https://openneuro.org/datasets/ds004666",
    "https://github.com/lemomo-ai/lemo-opuscar",
    "https://chengjinlii.github.io/SlicerDDSurfer/",
    "https://chengjinlii.github.io/SlicerDDSurfer/assets/img/social.jpg",
}
PAGES_URL = "https://chengjinlii.github.io/SlicerDDSurfer/"
# Opus r1 N6: these URLs may appear only in the places named here (page, tag, attribute, extra test).
PLACED_URLS = {
    PAGES_URL: [("index.html", "link", "href", ("rel", "canonical")),
                ("index.html", "meta", "content", ("property", "og:url")),
                ("404.html", "a", "href", None)],
    PAGES_URL + "assets/img/social.jpg": [("index.html", "meta", "content", ("property", "og:image"))],
    REPO + ".git": [],  # only in text, right after "git clone "
}

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
SKIP_TEXT = {"script", "style", "head", "title", "noscript"}


# ---------------------------------------------------------------- parsing
class Page(HTMLParser):
    """Collects what the checks need from one HTML file."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []          # (tag, attrs dict, line)
        self.stack = []
        self.errors = []
        self.ids = set()
        self.headings = []      # (level, text)
        self.text = []          # visible text pieces
        self.style_blocks = []
        self.script_blocks = []
        self._skip = 0
        self._in_style = False
        self._in_script = False
        self._heading = None
        self.transcript = []    # li texts inside details#transcript
        self._in_transcript = False
        self._transcript_depth = 0
        self._li = None
        self.doctype = ""
        self.extra_text = []    # alt, aria-label, title attributes, meta content
        self.title_text = []
        self._in_title = False

    def handle_decl(self, decl):
        self.doctype = decl

    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        self.tags.append((tag, a, self.getpos()[0]))
        for attr in ("alt", "aria-label", "title"):
            if a.get(attr):
                self.extra_text.append(a[attr])
        if tag == "meta" and a.get("content"):
            key = a.get("name", "") or a.get("property", "")
            if key == "description" or key.startswith(("og:", "twitter:")):
                self.extra_text.append(a["content"])
        if tag == "title":
            self._in_title = True
        if "id" in a:
            if a["id"] in self.ids:
                self.errors.append("duplicate id %r" % a["id"])
            self.ids.add(a["id"])
        if tag not in VOID:
            self.stack.append(tag)
        if tag in SKIP_TEXT:
            self._skip += 1
        if tag == "style":
            self._in_style = True
            self.style_blocks.append("")
        if tag == "script":
            self._in_script = True
            self.script_blocks.append("")
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = (int(tag[1]), [])
        if tag == "details" and a.get("id") == "transcript":
            self._in_transcript = True
            self._transcript_depth = len(self.stack)
        if self._in_transcript and tag == "li":
            self._li = []

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append("unclosed <%s> before </%s> (line %d)" % (
                    self.stack.pop(), tag, self.getpos()[0]))
            self.stack.pop()
        else:
            self.errors.append("stray </%s> (line %d)" % (tag, self.getpos()[0]))
        if tag in SKIP_TEXT:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "style":
            self._in_style = False
        if tag == "script":
            self._in_script = False
        if self._heading and tag == "h%d" % self._heading[0]:
            self.headings.append((self._heading[0], "".join(self._heading[1]).strip()))
            self._heading = None
        if self._in_transcript and tag == "li" and self._li is not None:
            self.transcript.append(" ".join("".join(self._li).split()))
            self._li = None
        if self._in_transcript and tag == "details":
            self._in_transcript = False

    def handle_data(self, data):
        if self._in_title:
            self.title_text.append(data)
        if self._in_style:
            self.style_blocks[-1] += data
        if self._in_script:
            self.script_blocks[-1] += data
        if self._heading is not None:
            self._heading[1].append(data)
        if self._li is not None:
            self._li.append(data)
        if not self._skip:
            self.text.append(data)

    def close(self):
        super().close()
        for t in self.stack:
            self.errors.append("unclosed <%s> at end of file" % t)

    def visible_text(self):
        return " ".join(" ".join(self.text).split())

    def wide_text(self):
        """Text content plus alt, aria-label, title attributes, <title> and meta content."""
        parts = [self.visible_text()] + self.extra_text + ["".join(self.title_text)]
        return " ".join(" ".join(parts).split())


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


JS_FILE = os.path.join(DOCS, "assets", "js", "site.js")
JS_STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"")


def js_literals():
    """String literals in site.js (comments removed first)."""
    if not os.path.isfile(JS_FILE):
        return []
    src = read(JS_FILE)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)^\s*//.*$", " ", src)
    return [m.group(1) if m.group(1) is not None else m.group(2) for m in JS_STRING.finditer(src)]


def wide_text(pages):
    """The 'visible text' of SPEC 7.1 checks 10 and 11."""
    parts = [p.wide_text() for _, p in pages] + js_literals()
    return " ".join(" ".join(parts).split())


def parse(path):
    p = Page()
    raw = read(path)
    p.feed(raw)
    p.close()
    return p, raw


def all_files(top=DOCS):
    for d, _, names in os.walk(top):
        for n in names:
            yield os.path.join(d, n)


# ---------------------------------------------------------------- results
results = []
# Opus r11 3, r13 1: main() sets "compared" on the line above the run-order comparison; a check that runs after that
# fails. It sets "summary" on the line above the summary; a check that runs after that is not counted, so it prints its
# FAIL and exits 1.
RUN = {"compared": False, "summary": False}


def check(name):
    def deco(fn):
        def run(*a, **k):
            if RUN["summary"]:
                print("FAIL %s - runs after the summary of main() started" % name)
                sys.exit(1)
            if RUN["compared"]:
                results.append(("FAIL", name, "runs after the run-order comparison in main()"))
                return
            try:
                out = fn(*a, **k)
            except Exception as exc:  # a crashing check is a failing check
                results.append(("FAIL", name, "exception: %r" % (exc,)))
                return
            if out is None:
                results.append(("PASS", name, ""))
            elif isinstance(out, tuple) and out[0] == "SKIP":
                results.append(("SKIP", name, out[1]))
            else:
                results.append(("FAIL", name, out))
        run.__name__ = fn.__name__
        run.check_name = name
        run.fn = fn  # the check without the wrapper, for the self-test in main()
        return run
    return deco


def fail_list(items):
    return "; ".join(items[:8]) + (" (+%d more)" % (len(items) - 8) if len(items) > 8 else "")


# ---------------------------------------------------------------- checks
@check("html_basics")
def html_basics(idx, raw_idx, p404, raw_404):
    problems = []
    for label, p, raw in (("index", idx, raw_idx), ("404", p404, raw_404)):
        dup = [e for e in p.errors if e.startswith("duplicate id")]
        if dup:
            problems.append("%s: every id must be unique: %s" % (label, fail_list(dup)))
        other = [e for e in p.errors if e not in dup]
        if other:
            problems.append("%s: %s" % (label, fail_list(other)))
        if not raw.lstrip().lower().startswith("<!doctype html>"):
            problems.append("%s: missing <!doctype html>" % label)
        html_tags = [a for t, a, _ in p.tags if t == "html"]
        if not html_tags or html_tags[0].get("lang") != "en":
            problems.append('%s: <html lang="en"> missing' % label)
        titles = re.findall(r"<title>(.*?)</title>", raw, re.S)
        if not titles or not titles[0].strip():
            problems.append("%s: empty <title>" % label)
        metas = {a.get("name"): a for t, a, _ in p.tags if t == "meta" and a.get("name")}
        if "viewport" not in metas:
            problems.append("%s: no viewport meta" % label)
        if not metas.get("description", {}).get("content", "").strip():
            problems.append("%s: no description meta" % label)
        if not any(t == "meta" and a.get("charset", "").lower() == "utf-8" for t, a, _ in p.tags):
            problems.append("%s: no charset utf-8" % label)
    h1 = [h for h in idx.headings if h[0] == 1]
    if len(h1) != 1:
        problems.append("index: %d <h1>, need exactly 1" % len(h1))
    for label, p in (("index", idx), ("404", p404)):
        prev = 0
        for level, text in p.headings:
            if level > prev + 1:
                problems.append("%s: heading level jumps h%d -> h%d (%r)" % (label, prev, level, text[:40]))
            prev = level
    return fail_list(problems) if problems else None


CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I)
CSS_IMPORT = re.compile(r"@import\s+(?:url\()?\s*['\"]?([^'\")\s;]+)", re.I)


def is_absolute(u):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", u)) or u.startswith("//")


def resolve_local(base_file, ref):
    """Return the absolute file path a local reference points to."""
    path = unquote(urlsplit(ref).path)
    if path == "":
        return base_file
    if path.startswith("/"):
        target = os.path.join(DOCS, path.lstrip("/"))
    else:
        target = os.path.normpath(os.path.join(os.path.dirname(base_file), path))
    if os.path.isdir(target):
        target = os.path.join(target, "index.html")
    return target


@check("local_refs")
def local_refs(pages):
    problems = []
    for path, p in pages:
        rel = os.path.relpath(path, ROOT)
        refs = []
        for tag, a, line in p.tags:
            for attr in ("href", "src", "poster"):
                if attr in a:
                    refs.append((attr, a[attr], line))
            if "srcset" in a:
                for part in a["srcset"].split(","):
                    if part.strip():
                        refs.append(("srcset", part.strip().split()[0], line))
            # Codex r1 B2: CSS url() in a style attribute counts like one in a <style> block.
            for m in CSS_URL.finditer(a.get("style", "")):
                refs.append(("style-url", m.group(2), line))
        for block in p.style_blocks:
            for m in CSS_URL.finditer(block):
                refs.append(("css-url", m.group(2), 0))
        for attr, ref, line in refs:
            if not ref or is_absolute(ref):
                continue
            if ref.startswith("#"):
                if ref != "#" and ref[1:] not in p.ids:
                    problems.append("%s:%s %s=%r has no matching id" % (rel, line, attr, ref))
                continue
            target = resolve_local(path, ref)
            inside = os.path.commonpath([DOCS, target]) == DOCS
            if not inside or not os.path.isfile(target):
                problems.append("%s:%s %s=%r does not resolve to a file in docs/" % (rel, line, attr, ref))
            # Codex r1 B5: a fragment after a page's file name must name an id in that page.
            elif urlsplit(ref).fragment and target.endswith(".html"):
                if unquote(urlsplit(ref).fragment) not in parse(target)[0].ids:
                    problems.append("%s:%s %s=%r has no matching id in %s" % (rel, line, attr, ref,
                                                                           os.path.relpath(target, ROOT)))
    for css in (f for f in all_files() if f.endswith(".css")):
        text = read(css)
        for m in CSS_URL.finditer(text):
            ref = m.group(2)
            if not ref or is_absolute(ref) or ref.startswith("#"):
                continue
            target = resolve_local(css, ref)
            inside = os.path.commonpath([DOCS, target]) == DOCS  # Codex r1 B4: inside docs/ too
            if not inside or not os.path.isfile(target):
                problems.append("%s url(%r) does not resolve to a file in docs/" % (os.path.relpath(css, ROOT), ref))
    return fail_list(problems) if problems else None


# XML namespace URIs (for example in inline SVG) are identifiers, not requests.
NAMESPACE_PREFIXES = ("http://www.w3.org/",)

URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>)`\\]+|https?://[^\s\"'<>)`\\]+")


@check("external_urls")
def external_urls(pages):
    problems = []
    texts = []
    for path, p in pages:
        texts.append((path, read(path)))
    for f in all_files():
        if f.endswith((".css", ".js")):
            texts.append((f, read(f)))
    for path, text in texts:
        rel = os.path.relpath(path, ROOT)
        for m in re.finditer(r"https?://[^\s\"'<>)`\\]+", text):
            url = m.group(0).rstrip(".,;:")
            if url.startswith(NAMESPACE_PREFIXES):
                continue
            if url not in ALLOWED_URLS:
                problems.append("%s: URL not in the allowed set: %s" % (rel, url))
        for m in re.finditer(r"(?<![:\w])//[a-zA-Z0-9.-]+\.[a-z]{2,}/", text):
            problems.append("%s: protocol-relative URL %s" % (rel, m.group(0)))
        # Opus r1 N6: the Pages URLs and the .git URL only where PLACED_URLS allows them.
        found = {}
        for m in re.finditer(r"https?://[^\s\"'<>)`\\]+", text):
            url = m.group(0).rstrip(".,;:")
            if url in PLACED_URLS:
                found[url] = found.get(url, 0) + 1
        page = dict(pages).get(path)
        for url, n in found.items():
            allowed = 0 if PLACED_URLS[url] else len(re.findall(r"git clone " + re.escape(url) + r"(?![^\s<])", text))
            for pname, ptag, pattr, pcond in PLACED_URLS[url]:
                if page is None or os.path.basename(path) != pname:
                    continue
                allowed += sum(1 for tag, a, line in page.tags if tag == ptag and a.get(pattr) == url
                               and (pcond is None or a.get(pcond[0]) == pcond[1]))
            if n > allowed:
                problems.append("%s: %s appears %d times, %d of them in an allowed place" % (rel, url, n, allowed))
    # Resource-loading tags and CSS must stay on this host.
    for path, p in pages:
        rel = os.path.relpath(path, ROOT)
        for tag, a, line in p.tags:
            if tag in ("link", "script", "img", "source", "video"):
                for attr in ("href", "src", "poster", "srcset"):
                    # Codex r1 B3: each srcset candidate is its own URL.
                    vals = [c.split()[0] for c in a.get(attr, "").split(",") if c.strip()] if attr == "srcset" \
                        else [a.get(attr, "")]
                    for v in vals:
                        if v and is_absolute(v):
                            if v.startswith("data:"):
                                continue
                            # Opus r1 N6: the canonical link names the Pages root, not any allowed URL.
                            if tag == "link" and a.get("rel") == "canonical" and v == PAGES_URL:
                                continue
                            problems.append("%s:%s <%s %s=%r> points to another host" % (rel, line, tag, attr, v))
        # Codex r1 B2: CSS in <style> blocks and style attributes stays on this host too.
        for css in list(p.style_blocks) + [a["style"] for tag, a, line in p.tags if "style" in a]:
            for m in CSS_URL.finditer(css):
                if is_absolute(m.group(2)) and not m.group(2).startswith("data:"):
                    problems.append("%s: inline CSS url(%s) is absolute" % (rel, m.group(2)))
            for m in CSS_IMPORT.finditer(css):
                if is_absolute(m.group(1)):
                    problems.append("%s: inline CSS @import %s is absolute" % (rel, m.group(1)))
    for f in all_files():
        if f.endswith(".css"):
            text = read(f)
            for m in CSS_URL.finditer(text):
                if is_absolute(m.group(2)) and not m.group(2).startswith("data:"):
                    problems.append("%s: CSS url(%s) is absolute" % (os.path.relpath(f, ROOT), m.group(2)))
                if m.group(2).startswith("data:"):
                    pass
            for m in CSS_IMPORT.finditer(text):
                if is_absolute(m.group(1)):
                    problems.append("%s: CSS @import %s is absolute" % (os.path.relpath(f, ROOT), m.group(1)))
    return fail_list(sorted(set(problems))) if problems else None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@check("film_bytes")
def film_bytes(film_arg):
    if not os.path.isfile(FILM):
        return "film file missing"
    size = os.path.getsize(FILM)
    if size != FILM_BYTES:
        return "size is %d bytes, need %d" % (size, FILM_BYTES)
    if film_arg:
        if not os.path.isfile(film_arg):
            return "--film path not found: %s" % film_arg
        if sha256(FILM) != sha256(film_arg):
            return "SHA-256 differs from %s" % film_arg
    return None


@check("film_faststart")
def film_faststart():
    boxes = []
    with open(FILM, "rb") as f:
        size_total = os.fstat(f.fileno()).st_size
        pos = 0
        while pos < size_total:
            f.seek(pos)
            head = f.read(16)
            if len(head) < 8:
                return "truncated box header at %d" % pos
            size, kind = struct.unpack(">I4s", head[:8])
            kind = kind.decode("latin-1")
            if size == 1:
                size = struct.unpack(">Q", head[8:16])[0]
            elif size == 0:
                size = size_total - pos
            if size < 8:
                return "bad box size %d for %r at %d" % (size, kind, pos)
            boxes.append(kind)
            pos += size
    if not boxes or boxes[0] != "ftyp":
        return "first box is %r, need ftyp (boxes: %s)" % (boxes[:1], boxes)
    if "moov" not in boxes or "mdat" not in boxes:
        return "moov or mdat missing (boxes: %s)" % boxes
    if boxes.index("moov") > boxes.index("mdat"):
        return "moov is after mdat (boxes: %s)" % boxes
    return None


@check("film_probe")
def film_probe():
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return ("SKIP", "ffprobe not on PATH")
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,codec_name,width,height,pix_fmt",
         "-of", "json", FILM],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    problems = []
    if not video:
        problems.append("no video stream")
    else:
        v = video[0]
        if (v.get("codec_name"), v.get("width"), v.get("height"), v.get("pix_fmt")) != (
                "h264", 1920, 1080, "yuv420p"):
            problems.append("video is %s %sx%s %s" % (
                v.get("codec_name"), v.get("width"), v.get("height"), v.get("pix_fmt")))
    if not audio or audio[0].get("codec_name") != "aac":
        problems.append("audio is not aac")
    dur = float(info["format"]["duration"])
    if abs(dur - 64.8) > 0.05:
        problems.append("duration %.3f s, need 64.8 +/- 0.05" % dur)
    return "; ".join(problems) if problems else None


def srt_cues(path):
    blocks = re.split(r"\n\s*\n", read(path).replace("\r\n", "\n").strip())
    cues = []
    for b in blocks:
        lines = b.split("\n")
        if len(lines) >= 3 and "-->" in lines[1]:
            cues.append(" ".join(l.strip() for l in lines[2:]))
    return cues


@check("transcript_matches_srt")
def transcript_matches_srt(idx):
    cues = srt_cues(SRT)
    if len(cues) != 12:
        return "SRT has %d cues, expected 12" % len(cues)
    page = idx.transcript
    if page != cues:
        for i, (a, b) in enumerate(zip(page, cues), 1):
            if a != b:
                return "item %d differs: page %r vs srt %r" % (i, a, b)
        return "page has %d items, SRT has %d" % (len(page), len(cues))
    return None


@check("sizes")
def sizes():
    total = 0
    for f in all_files():
        s = os.path.getsize(f)
        total += s
        if s > 50 * 1024 * 1024:
            return "%s is %d bytes (limit 50 MB)" % (os.path.relpath(f, ROOT), s)
    if total >= 100 * 1024 * 1024:
        return "docs/ is %d bytes (limit 100 MB)" % total
    return None


def image_size(path, is_bytes=False):
    if is_bytes:
        data = path
    else:
        with open(path, "rb") as f:
            data = f.read()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + seglen
    raise ValueError("not a PNG or JPEG")


# README N12 and N5: the image and font files are the recorded ones, so a re-made or swapped file is a deliberate
# change (update the hash here and the record in README).
IMAGE_SHA256 = {
    "icon-180.png": "3c8fc86e295be2e74d3e5e9e010cf6fa5570f0f0c8fed0ed8f49a44a4cba96c9",
    "icon-64.png": "889e9aa69a5c869fb245bfe1fa678da28644592a5923937868be914919bc7818",
    "idea.jpg": "a60f802c79c255a6e877453b964da68a20fe0258c3e8140866488b65a589a2ee",
    "out-connectome.jpg": "cb7b206fc7e40aea19b655b44e5f91b7f72acc66c8e7990c3ab78cef1c1e1922",
    "out-dec.jpg": "7b573b50a6565922bbec30c45d26ce704567daf98513b9f3da105c3593cc3455",
    "out-regions.jpg": "23f4792c09ba4fa675a93cfa9206967c6cefcfdc3df3c496a31f5e6049c7a395",
    "out-surfaces.jpg": "27b14e8d2c2e0dc203b8a8b16dd75e5b837ef4db3eb1b7d02ab32892019c6f6f",
    "out-tissue.jpg": "4aa00a9091114ade8212d0872c2f892621e978d5cd31d37fd12d9cf9b2f6a3d8",
    "out-tracts.jpg": "252bb7d56b6e4bd7da2192d9ad2954410189ee6e4ced9f80e417ebcfecd6f20e",
    "poster.jpg": "dea6cbd0b367e14e96f6ff8a3fad8affce3a09e1f9ea0e6b09bd2f17585a2364",
    "slicer.jpg": "cf8665ab28a533cc422b4acf33d52712edecf17271402095585c7a15d27c9051",
    "social.jpg": "efee53a920236153eb30de5c3289578f1bbb8d6e5a5c6e15c637a28aa36f2e9b",
}
FONT_SHA256 = {
    "IBMPlexMono-Medium.woff2": "8ce89898741b25f36a0648c4b9f0fdc8d37666349a65fef0eda486ebbc1dab4c",
    "IBMPlexMono-Regular.woff2": "61d88ee98544e257ae5063a3f61624238cc37094524aaf2191798d96dff00020",
    "Inter.woff2": "c9ab42b9c70be181e6cefb0a148647f5ad0d501e70703ef94d3b955a61d91f9c",
    "InterTight.woff2": "c5c50d01290f1fdeab74337afe6ad555a4560248a96bbc13c56fb0fb025e1cbe",
}


def pinned_files(d, names, table):
    problems = []
    for n in sorted(set(names) | set(table)):
        p = os.path.join(d, n)
        if n not in table:
            problems.append("%s is not recorded" % os.path.relpath(p, ROOT))
        elif not os.path.isfile(p):
            problems.append("%s is recorded but missing" % os.path.relpath(p, ROOT))
        elif sha256(p) != table[n]:
            problems.append("%s has SHA-256 %s, not the recorded %s" % (os.path.relpath(p, ROOT), sha256(p)[:12],
                                                                        table[n][:12]))
    return problems


@check("images")
def images(pages):
    problems = []
    for path, p in pages:
        rel = os.path.relpath(path, ROOT)
        for tag, a, line in p.tags:
            if tag != "img":
                continue
            src = a.get("src", "")
            if not a.get("alt", "").strip():
                problems.append("%s:%s %s has no alt" % (rel, line, src))
            try:
                w, h = int(a["width"]), int(a["height"])
            except (KeyError, ValueError):
                problems.append("%s:%s %s width/height missing or not integers" % (rel, line, src))
                continue
            if a.get("loading") != "lazy":
                problems.append("%s:%s %s lacks loading=lazy" % (rel, line, src))
            if src.startswith("data:"):
                import base64
                raw = base64.b64decode(src.split(",", 1)[1])
                iw, ih = image_size(raw, is_bytes=True)
            else:
                target = resolve_local(path, src)
                if not os.path.isfile(target):
                    problems.append("%s:%s %s missing" % (rel, line, src))
                    continue
                iw, ih = image_size(target)
            if abs((iw / ih) / (w / h) - 1) > 0.02:
                problems.append("%s:%s %s file %dx%d vs attributes %dx%d" % (rel, line, src, iw, ih, w, h))
    idir = os.path.join(DOCS, "assets", "img")
    problems += pinned_files(idir, [n for n in os.listdir(idir) if not n.startswith(".")], IMAGE_SHA256)
    return fail_list(problems) if problems else None


REQUIRED = ["at analysis time", "Private pre-release", "not a clinical assessment",
            "not certified", "24,000 of 130,780", "not installed silently", "in preparation",
            "display subset", "not acceptance by Slicer", "not run for the film",
            "No expert has reviewed", "SNR is higher than a typical single scan",
            "workarounds that are not in the repository", "must share one voxel grid"]
BANNED = [r"T1w?-free", r"T1-weighted-free", r"fully automatic", r"no registration",
          r"no preprocessing", r"U-shaped", r"\bthe first\b", r"\bthe only\b",
          r"clinical-grade", r"diagnos", r"FDA", r"available now", r"open[- ]source",
          r"\bfaster\b", r"\baccura(te|cy)\b", r"state[- ]of[- ]the[- ]art", r"cross-platform",
          r"(install|get|download)\w*\s+(SlicerDDSurfer|it)\b.{0,40}Extensions? (Manager|Catalog|Index)",
          r"(?<!not )(available )?(in|from|through) the (official )?Extensions? (Manager|Catalog)",
          # Opus code review r1 B1: the SlicerDDSurfer-models repository is public
          # (R/docs/release/VALIDATION_20260816.md:36), so the page must not call it private.
          r"model[- ]asset\w* repositor(y|ies)\b[^.]{0,40}\bprivate",
          # Opus r2 N5: and the reverse order ("private model-asset repository").
          r"\bprivate\b[^.]{0,40}\bmodel[- ]asset\w* repositor(y|ies)\b"]
EXT_MANAGER_SENTENCE = "Install SlicerDMRI and PyTorch from Slicer\u2019s Extension Manager."


@check("claims_required")
def claims_required(pages):
    text = wide_text(pages).lower()
    missing = [r for r in REQUIRED if r.lower() not in text]
    return "missing phrases: %s" % missing if missing else None


@check("claims_banned")
def claims_banned(pages):
    problems = []
    text = wide_text(pages)
    for pat in BANNED:
        for m in re.finditer(pat, text, re.I):
            ctx = text[max(0, m.start() - 30):m.end() + 30]
            problems.append("%r in ...%s..." % (pat, ctx))
    n = len(re.findall(r"Extension Manager", text, re.I))
    if n != 1:
        problems.append("'Extension Manager' occurs %d times, expected exactly 1" % n)
    elif EXT_MANAGER_SENTENCE not in text:
        problems.append("'Extension Manager' is not inside %r" % EXT_MANAGER_SENTENCE)
    return fail_list(problems) if problems else None


@check("no_local_paths")
def no_local_paths():
    needles = [b"/Volumes/", b"/Users/", b"/private/tmp", b"file://"]
    problems = []
    for f in all_files():
        with open(f, "rb") as fh:
            data = fh.read()
        for n in needles:
            if n in data:
                problems.append("%s contains %s" % (os.path.relpath(f, ROOT), n.decode()))
    return fail_list(problems) if problems else None


@check("links_safe")
def links_safe(pages):
    problems = []
    for path, p in pages:
        for tag, a, line in p.tags:
            if a.get("target") == "_blank" and "noopener" not in a.get("rel", "").split():
                problems.append("%s:%s target=_blank without rel=noopener (%s)" % (
                    os.path.basename(path), line, a.get("href", "")))
    return fail_list(problems) if problems else None


@check("fonts_licensed")
def fonts_licensed():
    fdir = os.path.join(DOCS, "assets", "fonts")
    woffs = [n for n in os.listdir(fdir) if n.endswith(".woff2")]
    if not woffs:
        return "no .woff2 files found"
    problems = []
    for n in woffs:
        family = n[:-len(".woff2")].split("-")[0]
        if not os.path.isfile(os.path.join(fdir, "OFL-%s.txt" % family)):
            problems.append("%s has no OFL-%s.txt" % (n, family))
    problems += pinned_files(fdir, woffs, FONT_SHA256)
    # README N5: SIL OFL 1.1 bars the Reserved Font Name "Plex" from a modified version (our subset).
    css = read(os.path.join(DOCS, "assets", "css", "site.css"))
    for m in re.finditer(r"@font-face\s*\{[^}]*?font-family:\s*([^;]+);", css):
        if "plex" in m.group(1).lower():
            problems.append("site.css @font-face family %s keeps the Reserved Font Name Plex" % m.group(1).strip())
    return fail_list(problems) if problems else None


@check("menu_focus_wording")
def menu_focus_wording():
    # Opus r4 B2: the focusout comment, README and SPEC §4 said the click handlers deal with a focus change to
    # nothing; none closes the menu then. All three must state the behaviour as it is.
    # Opus r6 1: in README only the Opus N3 note states the rule; the backlog entries may quote either wording.
    # Review of 90a6a03 (Codex P1): SPEC §7.1 item 15 quotes the phrase, so in SPEC only §4 counts.
    want = "a focus change to nothing does not close it"
    old = "left to the click handlers"
    problems = []
    for rel in ("docs/assets/js/site.js", "README.md", "SPEC.md"):
        text = read(os.path.join(ROOT, rel))
        if rel == "README.md":
            m = re.search(r"(?ms)^- Opus N3 \(P2\).*?(?=^(?! )|\Z)", text)
            if not m:
                problems.append("README.md has no 'Opus N3' note")
                continue
            rel, text = "README.md (Opus N3 note)", m.group(0)
        elif rel == "SPEC.md":
            start = text.find("\n## 4. ")
            end = text.find("\n## 5. ", start + 1)
            if start < 0 or end < 0:
                problems.append("SPEC.md has no §4 / §5 headings")
                continue
            rel, text = "SPEC.md (§4)", text[start:end]
        text = " ".join(text.split())
        if want not in text:
            problems.append("%s lacks %r" % (rel, want))
        if old in text:
            problems.append("%s still says %r" % (rel, old))
    return fail_list(problems) if problems else None


# The checks in SPEC v2 §7.1 (items 1-14). SPEC §9 must record each check added later as "item <n>
# `<name>`", with n its §7.1 number (see spec_lists_checks). The phrase wraps across two comment lines on
# purpose: backlog_wording must remove the comment marks to find it (README backlog r10 3).
V2_CHECKS = ("html_basics", "local_refs", "external_urls", "film_bytes", "film_faststart", "film_probe",
             "transcript_matches_srt", "sizes", "images", "claims_required", "claims_banned", "no_local_paths",
             "links_safe", "fonts_licensed")
# Opus r8 2: item 15 reads SPEC only in §4 because of the Codex P1 of the 90a6a03 review. For a check here, a §9
# paragraph that records it must cite the review that set its scope.
SECTION9_SOURCES = {"menu_focus_wording": "Codex P1 of the 90a6a03 review"}


@check("spec_lists_checks")
def spec_lists_checks(names):
    # Opus r6 2: SPEC §7.1 listed 14 checks while this script ran 15. Every check that runs must be listed there,
    # numbered 1..n in order, and nothing else.
    spec = read(os.path.join(ROOT, "SPEC.md"))
    start = spec.find("### 7.1 ")
    end = spec.find("### 7.2 ", start)
    if start < 0 or end < 0:
        return "SPEC.md has no §7.1 / §7.2 headings"
    items = re.findall(r"(?m)^(\d+)\. `(\w+)`", spec[start:end])
    listed = [n for _, n in items]
    problems = []
    if [int(i) for i, _ in items] != list(range(1, len(items) + 1)):
        problems.append("§7.1 numbering is not 1..%d" % len(items))
    if listed != names:
        problems.append("§7.1 lists %s; the script runs %s" % (listed, names))
    # Opus r7 2: §9 had no line for items 15 and 16. Every check added after the v2 list must be recorded in §9.
    # Opus r8 1: a name in backticks anywhere in §9 passed; §9 must say "item <n> `<name>`", n its §7.1 number.
    s9 = spec.find("\n## 9. ")
    if s9 < 0:
        problems.append("SPEC.md has no §9 heading")
    else:
        e9 = spec.find("\n## ", s9 + 1)
        # Opus r9 1: a line with only spaces or tabs also ends a paragraph, as in Markdown. The old .split("\n\n") did
        # not split there. (This comment also tests that backlog_wording ignores the comment lines of a code part.)
        paras = re.split(r"\n[ \t]*\n", spec[s9:] if e9 < 0 else spec[s9:e9])
        for i, n in items:
            if n in V2_CHECKS:
                continue
            entry = r"\bitem\s+%s\s+`%s`" % (i, n)
            mine = [p for p in paras if re.search(entry, p)]
            if not mine:
                problems.append("§9 does not record item %s `%s`" % (i, n))
            elif n in SECTION9_SOURCES and not any(SECTION9_SOURCES[n] in " ".join(p.split()) for p in mine):
                problems.append("§9 paragraph for item %s `%s` does not cite the %s" % (i, n, SECTION9_SOURCES[n]))
    return fail_list(problems) if problems else None


# Opus r11 1: the part of main() from the later loop to the count.
MAIN_TAIL = r"(?ms)^    for f in later:.*?(?=^    failed = 0)"
S9_R11_R12 = r"(?ms)^After code review \(2026-10-21, README backlog r11 1–4 and r12 1–4\).*?(?=\n\n|\Z)"

# Fixes from the README review backlog that only a text check can hold (wording, and code lines that guard a fix):
# (finding, file, the part of the file the finding names as a regex, the phrase that must be there, the phrase that
# must not be: a string, a compiled regex, or None). In a .py part, a part made of comment lines loses its comment
# marks, and a part that holds code loses its comments (code_text); then the part is whitespace-normalized.
WORDING_FIXES = (
    ("r9 2", "SPEC.md", r"(?ms)^16\. `spec_lists_checks`.*?(?=^(?! )|\Z)",
     "a §9 paragraph that records item 15", "the §9 paragraph that records item 15"),
    ("r9 3", "README.md", r"(?ms)^- r8 1 \(P3\).*?(?=^(?! )|\Z)",
     "only in passing, without recording the item, still passes", None),
    ("r9 4", "tests/check_site.py", r"(?m)(?:^#.*\n)+(?=V2_CHECKS = )",
     "item <n> `<name>`", "needs a line in SPEC §9"),
    # Opus r11 2: the old split is banned in both quote styles.
    ("r10 1", "tests/check_site.py", r"(?ms)^def spec_lists_checks\(.*?(?=^\S)",
     r're.split(r"\n[ \t]*\n"', re.compile(r"""\.split\((["'])\\n\\n\1\)""")),
    # Opus r11 1: only the lines from the later loop to the count, so a comparison moved below the count fails.
    ("r10 2", "tests/check_site.py", MAIN_TAIL, "if ran != checked:", None),
    ("r12 2", "tests/check_site.py", MAIN_TAIL,
     'results.append(("FAIL", "spec_lists_checks", "the checks that ran', None),
    ("r11 3", "tests/check_site.py", MAIN_TAIL, 'RUN["compared"] = True', None),
    # Opus r13 1: the run-order flag is on the line above the comparison.
    ("r13 1", "tests/check_site.py", MAIN_TAIL,
     'RUN["compared"] = True ran = [r[1] for r in results] if ran != checked:', None),
    # Review of 5989f8b (Opus P1 B1): the summary flag keeps its indent and stays on the line above failed = 0.
    ("r13 1", "tests/check_site.py", r'(?m)^    RUN\["summary"\] = True\n(?=    failed = 0)',
     'RUN["summary"] = True', None),
    # Found in the fix round of the 8d0597f review: "ran = checked" would switch off the comparison in one edit.
    ("r10 2", "tests/check_site.py", MAIN_TAIL, "ran = [r[1] for r in results]", None),
    ("r11 3", "tests/check_site.py", r"(?ms)^def check\(.*?(?=^\S)", 'if RUN["compared"]:', None),
    # Review of 8d0597f (Codex P1): pin the action too, not only the condition.
    ("r11 3", "tests/check_site.py", r"(?ms)^def check\(.*?(?=^\S)",
     'results.append(("FAIL", name, "runs after the run-order comparison', None),
    # Opus r13 1: a check that runs after the summary started prints its FAIL and exits 1. Review of 5989f8b (Opus P1
    # B2): that test comes before the "compared" test, which would catch the check first. Opus r16 1: the locator
    # keeps the indent, so the "compared" test cannot move under the summary test, after sys.exit(1). Opus r18 2: and
    # it starts right below def run, so a copy elsewhere, or a line added above the test, does not count.
    ("r16 1", "tests/check_site.py",
     r'(?m)(?<=^        def run\(\*a, \*\*k\):\n)'
     r'            if RUN\["summary"\]:\n                print\(.*\n                sys\.exit\(1\)\n'
     r'            if RUN\["compared"\]:\n',
     'if RUN["summary"]: print("FAIL %s - runs after the summary of main() started" % name) sys.exit(1)'
     ' if RUN["compared"]:', None),
    ("r10 4", "tests/check_site.py", r"(?m)(?:^#.*\n)+(?=SECTION9_SOURCES = )",
     "a §9 paragraph that records it", "The §9 paragraph that"),
    ("r10 4", "README.md", r"(?ms)^- r8 2 \(P3\).*?(?=^(?! )|\Z)",
     "needs a §9 paragraph that records item 15", "needs the §9 paragraph that records item 15"),
    ("r10 5", "SPEC.md", r"(?ms)^17\. `backlog_wording`.*?(?=^(?! )|\Z)",
     "and, where there is one, the old phrase is not", "is there and the old phrase is not"),
    ("r10 5", "README.md", r"(?ms)^- Test for r9 2–4: .*?(?=^(?! )|\Z)",
     "the fixed phrase and, where there is one, the old phrase", "the fixed phrase and the old phrase"),
    ("r11 4", "tests/check_site.py", r"(?m)(?<=def backlog_wording\(rows=WORDING_FIXES\):\n)(?:[ \t]*#.*\n)+",
     "each fix in WORDING_FIXES", "each wording fix stays in place"),
    ("r12 1", "SPEC.md", r"(?ms)^17\. `backlog_wording`.*?(?=^(?! )|\Z)",
     "code inside a string still counts", "so commented-out code does not count"),
    ("r12 1", "SPEC.md", r"(?ms)^After code review of af78411 .*?(?=\n\n|\Z)",
     "code commented out with whole `#` lines", "so commented-out code does not satisfy a pin"),
    # Opus r14 4: anchored on the words of the af78411 bullet; the review records after it start the same way.
    ("r12 3", "README.md",
     r"(?ms)^- Codex P1 \(Opus: P2\), fixed in the fix round: in a code row, a pinned phrase inside a comment"
     r".*?(?=^(?! )|\Z)",
     "and the old split put back with single quotes", None),
    ("r12 4", "tests/check_site.py", r"(?m)(?:^[ \t]*#.*\n)+(?=[ \t]*paras = re\.split)",
     r'The old .split("\n\n") did not split there', None),
    # Opus r12 1: the code rows use code_text, and the sample test stays.
    ("r12 1", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)", "part = code_text(part)", None),
    ("r12 1", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)", "if sample != CODE_SAMPLE_TEXT:", None),
    # Review of 8d0597f (Codex P1): pin how the sample is made and how a mismatch is reported.
    ("r12 1", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)",
     'sample = " ".join(code_text(CODE_SAMPLE).split())', None),
    ("r12 1", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)",
     'problems.append("the comment remover gives', None),
    ("r13 2", "README.md", r"(?ms)^- r11 2 \(P3\)\..*?(?=^(?! )|\Z)",
     "Code pins accept dead code and other spellings", None),
    ("r13 3", "SPEC.md", S9_R11_R12, "`part = code_text(part)`", None),
    ("r13 3", "SPEC.md", S9_R11_R12, "`if sample != CODE_SAMPLE_TEXT:`", None),
    # Opus r14 3: the sample keeps its trailing comment, so a whole-line remover still fails it.
    ("r14 3", "tests/check_site.py", r"(?m)^CODE_SAMPLE = .*$", "x = 1 # a trailing comment", None),
    ("r14 4", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)",
     'if len(found) > 1: problems.append("%s: %s has %d parts that match', None),
    ("r14 5", "SPEC.md", r"(?ms)^After code review of 8d0597f .*?(?=\n\n|\Z)",
     "which the author found in the fix round", None),
    ("r14 1", "README.md", r"(?ms)^- r11 2 \(P3\)\..*?(?=^(?! )|\Z)", "This holds for every code pin", None),
    ("r14 6", "README.md", r"(?ms)^- For each of these (?:four edits|six runs).*?(?=^(?! )|\Z)",
     "For each of these six runs", "these four edits"),
    # Opus r16 2: r15 2 was closed in the fix round, so it sits with B1 and B2, not in the "Not fixed" list.
    ("r15 2", "README.md", r"(?ms)^### Review of the r13 fix \(commit 5989f8b.*?(?=^Not fixed)",
     "r15 2 (P3), closed by the B1 row", None),
    ("r15 2", "README.md",
     r"(?ms)^Not fixed \(non-blocking, from the Opus review; Codex found nothing\):\n- r15 1 .*?(?=^### |\Z)",
     "r15 1 (P3)", "r15 2 (P3)"),
    ("r16 3", "tests/check_site.py", r'(?m)(?:^[ \t]*#.*\n)+(?=    \("r13 1", "tests/check_site.py", MAIN_TAIL,\n)',
     "the run-order flag is on the line above the comparison.", "summary flag is in MAIN_TAIL"),
    # Opus r17 5: the self-test call in main() and its FAIL. Opus r19 4: the call is in a try, right above the test.
    ("r17 5", "tests/check_site.py", MAIN_TAIL,
     'if not all(w in got for w in ("lacks", "still says", "still matches")):'
     ' results.append(("FAIL", "backlog_wording",', None),
    ("r19 4", "tests/check_site.py", MAIN_TAIL,
     'try: got = backlog_wording.fn(WORDING_SELF_TEST) or "" except Exception as exc: got = "exception: %r" % (exc,)'
     ' if not all(', None),
    # Opus r17 2: the line that feeds the one-part rule, next to the test that uses it.
    ("r17 2", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)",
     "found = list(re.finditer(where, read(os.path.join(ROOT, rel)))) if not found:", None),
    # Codex r17 1: MAIN_TAIL has one start; the one-part rule fails a second one.
    # Opus r19 2: no $, as in MAIN_TAIL, so "for f in later: pass" is a second start too.
    ("r17 1", "tests/check_site.py", r"(?m)^    for f in later:", "for f in later:", None),
    ("r17 3", "README.md", r"(?ms)^- r11 2 \(P3\)\..*?(?=^(?! )|\Z)", "(for example `sample = CODE_SAMPLE_TEXT`",
     "for example `ran = checked`"),
    ("r17 4", "README.md", r"(?ms)^- r14 3 \(P2\)\..*?(?=^(?! )|\Z)", "the row reads the source text", None),
    # Review of 49681a8 (Codex P1, Opus P1 B1; README r19 1): the normal call goes through every row of
    # WORDING_FIXES, and main() checks the count.
    ("r19 1", "tests/check_site.py", r"(?ms)^def backlog_wording\(.*?(?=^\S)",
     'WORDING_RUN["rows"] = 0 for finding, rel, where, want, banned in rows: WORDING_RUN["rows"] += 1', None),
    ("r19 1", "tests/check_site.py", MAIN_TAIL,
     'if WORDING_RUN["rows"] != len(WORDING_FIXES): results.append(("FAIL", "backlog_wording",', None),
    # Re-review of afca992 (Opus P1 B1; README r20 1): the count test keeps the indent of main()'s body, so it
    # cannot move into the "if ran != checked:" block above it.
    ("r20 1", "tests/check_site.py",
     r'(?m)^    if WORDING_RUN\["rows"\] != len\(WORDING_FIXES\):\n'
     r'(?=        results\.append\(\("FAIL", "backlog_wording",)',
     'if WORDING_RUN["rows"] != len(WORDING_FIXES):', None),
    ("r18 1", "README.md", r"(?ms)^- r16 4 \(information\): no change.*?(?=^(?! )|\Z)",
     "a trailing comment on a pinned line other than the print line", None),
    ("r19 3", "README.md", r"(?ms)^- r17 5 \(outside the bca6f20 diff; since 84c2ffd\)\..*?(?=^(?! )|\Z)",
     "together with an edit to the “lacks” line or the return line", "together with an edit to a reporting line"),
    ("r19 5", "README.md", r"(?ms)^- r17 3 \(P3\)\. \*\*Fixed.*?(?=^(?! )|\Z)",
     "no longer lists `ran = checked` as an example", "drops `ran = checked`"),
    ("r19 5", "README.md", r"(?ms)^- r14 2 \(P2/P3\)\. Recorded.*?(?=^(?! )|\Z)",
     "(`sample = CODE_SAMPLE_TEXT`, `problems = []`)", "(`ran = checked`, `sample"),
    # Opus r20 2: the self-test keeps the indent of main()'s body, so it cannot move into the count test above it.
    ("r20 2", "tests/check_site.py",
     r'(?m)^    try:\n        got = backlog_wording\.fn\(WORDING_SELF_TEST\) or ""\n    except Exception as exc:.*\n'
     r'        got = .*\n(?=    if not all\(w in got)',
     'try: got = backlog_wording.fn(WORDING_SELF_TEST) or "" except Exception as exc:', None),
    # README N12, N15 and N5: the records of the re-made surfaces image, the tools and the renamed subset.
    ("N12", "SPEC.md", r"(?m)^\| out-surfaces\.jpg \| [0-9].*$", "| out-surfaces.jpg | 35.4 |", "| 34.8 |"),
    ("N12", "README.md", r"(?m)^\| out-surfaces\.jpg \|.*$", "| out-surfaces.jpg | 35.4 |", "| 34.8 |"),
    ("N15", "SPEC.md", r"(?ms)^## 3\. Images.*?(?=^\| File)", "written with Pillow 13.0.0", None),
    ("N15", "SPEC.md", r"(?ms)^Fonts \(README N15, N5\):.*?(?=\n\n)", "fontTools 4.67.0", None),
    ("N5", "docs/index.html", r"(?m)^.*Fonts: Inter, Inter Tight, IBM Plex Mono.*$", "renamed “DDS Mono”", None),
    ("r20 6", "SPEC.md", r"(?ms)^17\. `backlog_wording`.*?(?=^(?! )|\Z)",
     "went through fewer or more rows than `WORDING_FIXES` holds", "did not go through every row of `WORDING_FIXES`"),
    ("r20 6", "SPEC.md", r"(?ms)^After code review of 49681a8 .*?(?=\n\n|\Z)",
     "went through fewer or more rows than `WORDING_FIXES` holds", "did not go through every row of `WORDING_FIXES`"),
)

# Opus r12 1: a sample for the comment remover of a code part: a trailing comment and a comment line go, a # inside a
# string stays.
CODE_SAMPLE = 'x = 1  # a trailing comment\n# a comment line\ny = "# not a comment"\n'
CODE_SAMPLE_TEXT = 'x = 1 y = "# not a comment"'

# Opus r17 5: no row can guard the lines that report every row (the "lacks", "still says" and "still matches" lines,
# and the return line), so main() runs backlog_wording on these rows, which must give all three problems.
WORDING_SELF_TEST = (
    ("self-test", "tests/check_site.py", r"(?m)^CODE_SAMPLE_TEXT = .*$", "a phrase that this line does not hold",
     "CODE_SAMPLE_TEXT"),
    ("self-test", "tests/check_site.py", r"(?m)^CODE_SAMPLE_TEXT = .*$", "CODE_SAMPLE_TEXT",
     re.compile(r"SAMPLE_TEXT")),
)
# Review of 49681a8 (README r19 1): the rows that the last backlog_wording call went through; main() compares it
# with WORDING_FIXES.
WORDING_RUN = {"rows": 0}


def code_text(part):
    # Opus r12 1: blank out every COMMENT token (also at the end of a line). Code in a string still counts.
    lines = io.StringIO(part).readlines()  # the same lines that tokenize reads
    for tok in tokenize.generate_tokens(io.StringIO(part).readline):
        if tok.type == tokenize.COMMENT:
            (row, c0), (_, c1) = tok.start, tok.end
            lines[row - 1] = lines[row - 1][:c0] + " " * (c1 - c0) + lines[row - 1][c1:]
    return "".join(lines)


@check("backlog_wording")
def backlog_wording(rows=WORDING_FIXES):
    # README review backlog: each fix in WORDING_FIXES (wording, or a code line that guards a fix) stays in place, in
    # the part of the file that its row names.
    problems = []
    try:
        sample = " ".join(code_text(CODE_SAMPLE).split())
    except (tokenize.TokenError, SyntaxError) as exc:
        sample = "exception: %r" % (exc,)
    if sample != CODE_SAMPLE_TEXT:
        problems.append("the comment remover gives %r for its sample, not %r" % (sample, CODE_SAMPLE_TEXT))
    WORDING_RUN["rows"] = 0
    for finding, rel, where, want, banned in rows:
        WORDING_RUN["rows"] += 1
        found = list(re.finditer(where, read(os.path.join(ROOT, rel))))
        if not found:
            problems.append("%s: %s has no part that matches %r" % (finding, rel, where))
            continue
        # Opus r14 4: a row's part must be one part of the file, so that the row cannot test another part by chance.
        if len(found) > 1:
            problems.append("%s: %s has %d parts that match %r, not one" % (finding, rel, len(found), where))
            continue
        part = found[0].group(0)
        if rel.endswith(".py"):
            if all(re.match(r"[ \t]*#", ln) for ln in part.splitlines() if ln.strip()):
                # Opus r10 3: a part made of comment lines is wording. Drop the comment marks, so that a phrase may wrap
                # across two comment lines.
                part = re.sub(r"(?m)^[ \t]*# ?", "", part)
            else:
                # Review of af78411 (Codex P1): in a part that holds code, only code counts. Opus r12 1: drop every
                # comment, also one at the end of a line.
                try:
                    part = code_text(part)
                except (tokenize.TokenError, SyntaxError) as exc:
                    problems.append("%s: %s part does not tokenize: %r" % (finding, rel, exc))
                    continue
        text = " ".join(part.split())
        if want not in text:
            problems.append("%s: %s lacks %r" % (finding, rel, want))
        if isinstance(banned, re.Pattern) and banned.search(text):
            problems.append("%s: %s still matches %r" % (finding, rel, banned.pattern))
        elif isinstance(banned, str) and banned in text:
            problems.append("%s: %s still says %r" % (finding, rel, banned))
    return fail_list(problems) if problems else None


# ---------------------------------------------------------------- main
def main(argv):
    film_arg = None
    if "--film" in argv:
        i = argv.index("--film")
        if i + 1 >= len(argv):
            print("usage: check_site.py [--film PATH]")
            return 2
        film_arg = argv[i + 1]
    idx, raw_idx = parse(INDEX)
    p404, raw_404 = parse(PAGE404)
    pages = [(INDEX, idx), (PAGE404, p404)]

    html_basics(idx, raw_idx, p404, raw_404)
    local_refs(pages)
    external_urls(pages)
    film_bytes(film_arg)
    film_faststart()
    film_probe()
    transcript_matches_srt(idx)
    sizes()
    images(pages)
    claims_required(pages)
    claims_banned(pages)
    no_local_paths()
    links_safe(pages)
    fonts_licensed()
    menu_focus_wording()
    # spec_lists_checks compares §7.1 with every check, so it also gets the names of the checks that run after it.
    later = [backlog_wording]
    checked = [r[1] for r in results] + ["spec_lists_checks"] + [f.check_name for f in later]
    spec_lists_checks(checked)
    for f in later:
        f()
    # Opus r10 2: spec_lists_checks took the names in `later` on trust. The checks that ran must be that list.
    # Opus r13 1: the flag goes up on the line above the comparison, so no check can run between the two.
    RUN["compared"] = True
    ran = [r[1] for r in results]
    if ran != checked:
        results.append(("FAIL", "spec_lists_checks", "the checks that ran %s differ from the list it checked %s"
                        % (ran, checked)))
    # Review of 49681a8 (README r19 1): the normal call went through the whole table (the self-test call below passes
    # its own rows).
    if WORDING_RUN["rows"] != len(WORDING_FIXES):
        results.append(("FAIL", "backlog_wording", "its normal call went through %d of the %d rows"
                        % (WORDING_RUN["rows"], len(WORDING_FIXES))))
    # Opus r17 5: backlog_wording must still report a missing phrase and a banned one (see WORDING_SELF_TEST).
    try:
        got = backlog_wording.fn(WORDING_SELF_TEST) or ""
    except Exception as exc:  # Opus r19 4: a crash here is a FAIL line, not a lost report
        got = "exception: %r" % (exc,)
    if not all(w in got for w in ("lacks", "still says", "still matches")):
        results.append(("FAIL", "backlog_wording", "its self-test rows give %r, not the three problems" % got))

    # Opus r13 1: from here on a result is not counted, so a check that runs now prints its FAIL and exits 1.
    RUN["summary"] = True
    failed = 0
    for status, name, reason in results:
        if status == "PASS":
            print("PASS %s" % name)
        elif status == "SKIP":
            print("SKIP %s - %s" % (name, reason))
        else:
            failed += 1
            print("FAIL %s - %s" % (name, reason))
    print("%d checks, %d failed" % (len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
