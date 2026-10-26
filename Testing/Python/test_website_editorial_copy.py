"""Keep the homepage aligned with the manuscript and current GUI entry points."""
import html
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
TITLE = ("SlicerDDSurfer: a T1-weighted-image-free 3D Slicer workflow for diffusion MRI "
         "anatomy, microstructure and connectivity analysis")


class WebsiteEditorialCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "docs/site/index.html").read_text(encoding="utf-8")

    def section(self, name):
        return re.search(r'<section\b[^>]*\bid="' + name + r'"[^>]*>(.*?)</section>',
                         self.source, re.S).group(1)

    def test_manuscript_title_in_hero_and_share_metadata(self):
        hero = re.search(r"<h1\b[^>]*>(.*?)</h1>", self.source, re.S).group(1)
        self.assertEqual(html.unescape(re.sub(r"<[^>]+>", "", hero)), TITLE)
        self.assertIn("<title>" + TITLE + "</title>", self.source)
        self.assertIn('property="og:title" content="' + TITLE + '"', self.source)

    def test_idea_section_and_dangling_navigation_are_removed(self):
        self.assertNotIn('id="idea"', self.source)
        self.assertNotIn('href="#idea"', self.source)

    def test_wmql_gallery_matches_latest_official_query_asset(self):
        card = re.search(r'<article class="tile tile-wmql">(.*?)</article>',
                         self.source, re.S).group(1)
        source = ROOT / "docs/figures/src/results/bu_wmql_ukf.jpg"
        published = ROOT / "docs/site/assets/img/res-wmql-ukf.jpg"
        receipt = json.loads((source.parent / "wmql_sources.json").read_text())
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

    def test_six_protocol_domains(self):
        workflows = self.section("workflows")
        cards = re.findall(r'<article class="wf-card">(.*?)</article>', workflows, re.S)
        self.assertEqual(len(cards), 6)
        self.assertEqual([re.search(r"<h3>(.*?)</h3>", c).group(1) for c in cards],
                         ["Preprocessing", "Microstructure", "Anatomy", "Tractography", "Bundles", "Connectome"])

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
        self.assertEqual(re.findall(r'<li id="ref-(\d+)"', cite), [str(i) for i in range(1, 36)])

    def test_setup_describes_current_gui_and_first_execution(self):
        start = self.section("start")
        for requirement in ("--slicer-version 5.10", "Additional module paths", "UKFTractography",
                            "nodif_brain_mask.nii.gz", "Prepare selected analysis environment",
                            "Results and QC", "--doctor", "--plan", "--execute", "--jobs 2"):
            self.assertIn(requirement, start)
        self.assertNotIn("Advanced settings › Results and QC", self.source)


if __name__ == "__main__":
    unittest.main()
