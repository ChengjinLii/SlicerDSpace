import copy
import unittest
import xml.etree.ElementTree as ET

from scripts.prepare_website_results import render, validate_static_svg

NS = 'http://www.w3.org/2000/svg'


class WebsiteResultsTests(unittest.TestCase):
    def fixture(self):
        root = ET.Element('svg', xmlns=NS)
        ET.SubElement(root, 'rect', width='100%', height='100%', fill='#fff')
        for index in range(5):
            ET.SubElement(root, 'rect', x=str(index), rx='16', fill='#0a0d12')
        ET.SubElement(root, 'image', href='data:image/jpeg;base64,dGVzdA==', x='12')
        ET.SubElement(root, 'text').text = 'WMQL'
        return ET.tostring(root)

    def test_only_background_and_panel_strokes_change(self):
        original = ET.fromstring(self.fixture())
        rendered = ET.fromstring(render(self.fixture()))
        self.assertEqual(rendered[0].get('fill'), '#06080b')
        for node in list(rendered)[1:6]:
            self.assertEqual(node.get('stroke'), '#ffffff')
            self.assertEqual(node.get('stroke-width'), '1.5')
        for before, after in zip(list(original)[6:], list(rendered)[6:]):
            self.assertEqual(ET.tostring(before), ET.tostring(after))

    def test_active_and_external_svg_elements_are_rejected(self):
        for tag, attrs in (('script', {}), ('foreignObject', {}),
                           ('image', {'href': 'https://example.org/private.png'}),
                           ('rect', {'onclick': 'alert(1)'})):
            root = ET.fromstring(self.fixture())
            ET.SubElement(root, '{' + NS + '}' + tag, attrs)
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_static_svg(root)

    def test_partial_overview_is_rejected(self):
        root = ET.fromstring(self.fixture())
        root.remove(root[1])
        with self.assertRaisesRegex(ValueError, 'five-panel'):
            render(ET.tostring(root))
