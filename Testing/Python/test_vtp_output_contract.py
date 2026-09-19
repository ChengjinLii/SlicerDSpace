"""Reject plausible VTP headers when their actual geometry is invalid."""

import tempfile
import unittest
from pathlib import Path

from shared.output_contracts import vtp_streamline_count
from vtp_fixture import vtp_lines


class VtpOutputContractTest(unittest.TestCase):
    def test_complete_geometry_and_empty_polydata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.vtp"
            for count in (0, 1, 3):
                path.write_text(vtp_lines(count))
                self.assertEqual(vtp_streamline_count(path), count)

    def test_rejects_header_only_truncation_nan_and_invalid_indices(self):
        valid = vtp_lines(1)
        corrupt = (
            '<VTKFile><PolyData><Piece NumberOfLines="100"/></PolyData></VTKFile>',
            valid[:len(valid) // 2],
            valid.replace('0 0 0 1 2 3', 'nan 0 0 1 2 3'),
            valid.replace('>0 1<', '>0 99<'),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle.vtp"
            for index, data in enumerate(corrupt):
                with self.subTest(index=index):
                    path.write_text(data)
                    self.assertIsNone(vtp_streamline_count(path))

    def test_compressed_binary_geometry(self):
        from vtkmodules.vtkIOXML import vtkXMLPolyDataReader, vtkXMLPolyDataWriter

        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "ascii.vtp", Path(tmp) / "compressed.vtp"
            source.write_text(vtp_lines(3))
            reader = vtkXMLPolyDataReader()
            reader.SetFileName(str(source))
            reader.Update()
            writer = vtkXMLPolyDataWriter()
            writer.SetFileName(str(target))
            writer.SetInputData(reader.GetOutput())
            writer.SetDataModeToAppended()
            writer.SetCompressorTypeToZLib()
            self.assertEqual(writer.Write(), 1)
            self.assertEqual(vtp_streamline_count(target), 3)


if __name__ == "__main__":
    unittest.main()
