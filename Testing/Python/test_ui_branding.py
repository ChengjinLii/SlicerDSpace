"""The module ships the same vector wordmark used by the homepage."""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class BrandingTest(unittest.TestCase):
    def test_vector_asset_is_identical_to_the_public_wordmark(self):
        artwork = ROOT / 'Resources/Icons/SlicerDSpace-wordmark.svg'
        self.assertEqual(artwork.read_bytes(),
                         (ROOT / 'docs/site/assets/img/slicerdspace-wordmark.svg').read_bytes())
        nodes = list(ET.fromstring(artwork.read_bytes()).iter())
        self.assertTrue(any(node.tag.endswith('path') for node in nodes))
        self.assertFalse(any(node.tag.endswith('image') for node in nodes))

    def test_packaged_resource_manifest_includes_the_svg(self):
        import json
        manifest = json.loads((ROOT / 'scripts/extension_runtime/runtime_resources.json').read_text())
        self.assertIn('Resources/Icons/SlicerDSpace-wordmark.svg', manifest['files'])


if __name__ == '__main__':
    unittest.main()
