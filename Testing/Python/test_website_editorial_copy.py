"""Keep the homepage aligned with the manuscript and current GUI entry points."""
import html
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TITLE = "SlicerDDSurfer"
SUBTITLE = ("A T1-weighted-image-free 3D Slicer workflow for diffusion MRI "
            "anatomy, microstructure and connectivity analysis")


class WebsiteEditorialCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "docs/site/index.html").read_text(encoding="utf-8")

    def section(self, name):
        return re.search(r'<section\b[^>]*\bid="' + name + r'"[^>]*>(.*?)</section>',
                         self.source, re.S).group(1)

    def test_product_title_and_manuscript_subtitle(self):
        hero = re.search(r"<h1\b[^>]*>(.*?)</h1>", self.source, re.S).group(1)
        self.assertEqual(html.unescape(re.sub(r"<[^>]+>", "", hero)), TITLE)
        self.assertIn("<title>" + TITLE + "</title>", self.source)
        self.assertIn('property="og:title" content="' + TITLE + '"', self.source)
        self.assertIn('<p class="subtitle">' + SUBTITLE + '</p>', self.source)

    def test_removed_sections_leave_no_dangling_navigation(self):
        for name in ("idea", "workflows", "status", "performance-notes", "slicer"):
            self.assertNotIn('id="' + name + '"', self.source)
            self.assertNotIn('href="#' + name + '"', self.source)
        self.assertNotIn("fig-route-guide.png", self.source)
        self.assertIn("fig-product-map.png", self.source)

    def test_methods_immediately_precede_references(self):
        main = self.source.split('<main id="main">', 1)[1].split('</main>', 1)[0]
        sections = re.findall(r'<section\b[^>]*\bid="([^"]+)"', main)
        self.assertEqual(sections[-2:], ["integrated", "cite"])

    def test_header_and_footer_use_the_reviewed_vector_logo_export(self):
        for css_class in ("brand", "foot-brand"):
            logo = re.search(r'class="' + css_class + r'"[^>]*>\s*<img\b([^>]+)>', self.source).group(1)
            self.assertIn('src="assets/img/logo-ddsurfer.png"', logo)
        record = json.loads((ROOT / "docs/website/logo_provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(record["source"], "docs/figures/logo-ref.svg")
        subprocess.run([sys.executable, "scripts/sync_website_logo.py", "--check"],
                       cwd=ROOT, check=True, capture_output=True, text=True)

    def test_wmql_gallery_matches_latest_official_query_asset(self):
        card = re.search(r'<article class="tile tile-wmql">(.*?)</article>',
                         self.source, re.S).group(1)
        source = ROOT / "docs/figures/src/results/bu_wmql_ukf.jpg"
        published = ROOT / "docs/site/assets/img/res-wmql-ukf.jpg"
        receipt = json.loads((source.parent / "wmql_sources.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["query_provenance"]["preset"], "official_multibundle")
        self.assertEqual(receipt["stills"]["bu_wmql_ukf"]["display"]["input_method"], "UKF")
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         receipt["stills"]["bu_wmql_ukf"]["display"]["jpeg_sha256"])
        self.assertEqual(published.read_bytes(), source.read_bytes())
        self.assertIn('src="assets/img/res-wmql-ukf.jpg"', card)
        self.assertIn('width="1852" height="1000"', card)
        self.assertIn("Official WMQL queries on UKF", card)
        self.assertNotIn("ddparcel_act", card)
        self.assertNotIn("res-wmql-csd.jpg", self.source)
        self.assertFalse((published.parent / "res-wmql-csd.jpg").exists())
        styles = (ROOT / "docs/site/assets/css/site.css").read_text(encoding="utf-8")
        self.assertRegex(styles, r"\.tile-wmql img\s*\{[^}]*object-fit:\s*contain")

    def test_integration_is_standalone_and_source_backed(self):
        integrated = self.section("integrated")
        methods = re.findall(r'<tr data-method="([^"]+)"', integrated)
        self.assertEqual(len(methods), 35)
        self.assertEqual(len(set(methods)), 35)
        for method in ("pnl_cnn", "localpca", "patch2self", "eddy", "topup", "dti",
                       "freewater", "noddi", "dki", "mkcurve", "ddseg", "ddparcel",
                       "ddsurfer", "surface_postprocess", "ukf", "saf", "wmql",
                       "wma", "tractcloud", "sift2", "scalar_length", "regional"):
            self.assertIn(method, methods)
        for row in re.findall(r'<tr data-method=.*?</tr>', integrated, re.S):
            self.assertRegex(row, r'href="#ref-\d+"')
        subprocess.run([sys.executable, "scripts/build_website_catalog.py", "--check"],
                       cwd=ROOT, check=True, capture_output=True, text=True)

    def test_integration_lists_resources_without_obsolete_status_badges(self):
        table = re.search(r'<table class="int-table">(.*?)</table>', self.source, re.S).group(1)
        for old in ("st-partial", "MATLAB", "no recorded run", "synthetic data only", "Partial:"):
            self.assertNotIn(old, table)
        self.assertIn("Runtime / access", table)
        self.assertIn("Python API", table)
        self.assertIn("UKF reference route", table)
        self.assertIn("full suite optional", table)

    def test_citations_use_one_uniform_numbered_list(self):
        cite = self.section("cite")
        self.assertNotIn("paper-grid", cite)
        self.assertEqual(cite.count('<ol class="ref-list">'), 1)
        self.assertEqual(re.findall(r'<li id="ref-(\d+)"', cite), [str(i) for i in range(1, 54)])
        self.assertNotIn("<details", cite)
        main = self.source.split('<main id="main">', 1)[1].split('</main>', 1)[0]
        self.assertEqual(re.findall(r'<section\b[^>]*\bid="([^"]+)"', main)[-1], "cite")

    def test_references_have_primary_links_and_no_dangling_ids(self):
        catalog = json.loads((ROOT / "docs/website/references.json").read_text(encoding="utf-8"))
        refs = {str(item["id"]) for item in catalog["references"]}
        self.assertEqual(refs, set(re.findall(r'<li id="ref-(\d+)"', self.source)))
        self.assertTrue(set(re.findall(r'href="#ref-(\d+)"', self.source)) <= refs)
        for item in catalog["references"]:
            self.assertTrue(item["url"].startswith("https://"))
            self.assertIn(html.escape(item["url"], quote=True), self.source)

    def test_subject_identity_does_not_dominate_main_copy(self):
        for name in ("top", "film", "outputs"):
            copy = self.section(name)
            self.assertNotIn("EDDEN sub-01", copy)
        self.assertIn('href="#ref-35"', self.source)

    def test_setup_describes_current_gui_and_first_execution(self):
        start = self.section("start")
        for requirement in ("--slicer-version 5.10", "Additional module paths", "UKFTractography",
                            "nodif_brain_mask.nii.gz", "Prepare selected analysis environment",
                            "Results and QC", "--doctor", "--plan", "--execute", "--jobs 2"):
            self.assertIn(requirement, start)
        self.assertNotIn("Advanced settings › Results and QC", self.source)


if __name__ == "__main__":
    unittest.main()
