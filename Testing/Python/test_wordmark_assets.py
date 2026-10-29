"""Transparent, font-independent wordmarks in the homepage and both READMEs."""

from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'docs/site/assets/img'


class WordmarkTests(unittest.TestCase):
    def test_outlined_transparent_variants_share_geometry(self):
        geometry = []
        palettes = []
        for name in ('slicerdspace-wordmark.svg', 'slicerdspace-wordmark-light.svg'):
            source = (ASSETS / name).read_text(encoding='utf-8')
            svg = ET.fromstring(source)
            self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
            viewbox = [float(v) for v in svg.attrib['viewBox'].split()]
            self.assertGreater(viewbox[2], 0)
            self.assertGreater(viewbox[3], 0)
            paths = []
            colors = set()
            for node in svg.iter():
                tag = node.tag.rsplit('}', 1)[-1]
                self.assertNotIn(tag, ('image', 'text', 'rect', 'script', 'foreignObject'))
                self.assertFalse(any(key.rsplit('}', 1)[-1] == 'href' for key in node.attrib))
                if tag == 'path':
                    self.assertTrue(node.attrib.get('d'))
                    paths.append(node.attrib['d'])
                if 'fill' in node.attrib and node.attrib['fill'] != 'none':
                    colors.add(node.attrib['fill'])
            self.assertTrue(paths)
            self.assertNotIn('base64', source)
            self.assertNotIn('font-family', source)
            geometry.append((viewbox, paths))
            palettes.append(colors)
        self.assertEqual(*geometry)
        self.assertNotEqual(*palettes)

    def test_readmes_show_themed_wordmark_before_the_introduction(self):
        for name in ('README.md', 'README.zh-CN.md'):
            source = (ROOT / name).read_text(encoding='utf-8')
            logo = source.index('src="docs/site/assets/img/slicerdspace-wordmark.svg"')
            film = source.index('SlicerDSpace_preview.gif')
            self.assertLess(logo, film)
            introduction = ('SlicerDSpace combines T1-weighted-image-free' if name == 'README.md'
                            else 'SlicerDSpace 将无需 T1 加权影像')
            self.assertLess(logo, source.index(introduction))
            self.assertIn('media="(prefers-color-scheme: dark)"', source)
            self.assertIn('media="(prefers-color-scheme: light)"', source)
            self.assertIn('srcset="docs/site/assets/img/slicerdspace-wordmark-light.svg"', source)

    def test_homepage_keeps_one_accessible_title(self):
        source = (ROOT / 'docs/site/index.html').read_text(encoding='utf-8')
        headings = re.findall(r'<h1\b[^>]*>(.*?)</h1>', source, re.S)
        self.assertEqual(len(headings), 1)
        self.assertIn('<span class="sr-only">SlicerDSpace</span>', headings[0])
        self.assertIn('src="assets/img/slicerdspace-wordmark-light.svg"', headings[0])
        self.assertIn('fetchpriority="high"', headings[0])


if __name__ == '__main__':
    unittest.main()
