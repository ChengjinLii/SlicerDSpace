"""Model output labels are distinct from the full FreeSurfer wmparc schema."""

import ast
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class DDParcelLabelContractTests(unittest.TestCase):
    def test_author_model_mapping_retains_callosal_192_and_generic_white_matter(self):
        loader = ROOT / 'anatomy/parcellation/data_loader/load_neuroimaging_data.py'
        function = next(node for node in ast.parse(loader.read_text(encoding='utf-8')).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'map_label2aparc_aseg')
        namespace = {'np': np}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(loader), 'exec'), namespace)
        merged = namespace['map_label2aparc_aseg'](np.arange(82).reshape(1, 1, 82))
        prediction = ast.parse((ROOT / 'anatomy/parcellation/DDSurfer_Pred.py').read_text(encoding='utf-8'))
        assignment = next(node for node in ast.walk(prediction) if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'labels_list' for target in node.targets))
        split = ast.literal_eval(assignment.value.args[0])
        expected = set(map(int, merged.ravel())) | {label + 1000 for label in split}
        self.assertEqual(len(expected - {0}), 101)
        self.assertTrue({2, 41, 192} <= expected)
        self.assertFalse({1004, 2004, 3004, 4004, 5001, 5002} & expected)
        self.assertFalse(any(3000 <= label < 5000 for label in expected))
        self.assertEqual(len(set(merged.ravel())), 82)


if __name__ == '__main__':
    unittest.main()
