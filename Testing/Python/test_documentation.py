"""Documentation structure, entry points and executable README examples."""

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import unittest
from urllib.parse import urlsplit

from scripts.audit_documentation import audit
from scripts.audit_slicer_extension_metadata import audit as audit_metadata
from shared.run_subject_pipeline_cli import build_parser, resolve_analysis_options


ROOT = Path(__file__).resolve().parents[2]
READMES = ('README.md', 'README.zh-CN.md')


class DocumentationTest(unittest.TestCase):
    def test_active_documents_are_consistent(self):
        result = audit()
        self.assertEqual(result["status"], "pass", result["findings"])

    def test_readme_preserves_extension_setup_metadata(self):
        result = audit_metadata(ROOT)
        self.assertEqual(result['status'], 'pass', result['findings'])

    def test_readme_technology_badges_match_both_languages(self):
        rendered = []
        for name in READMES:
            text = (ROOT / name).read_text(encoding='utf-8')
            masthead = text.split('</div>', 1)[0]
            badges = re.findall(r'\[!\[([^]]+)\]\((https://img\.shields\.io/[^)]+)\)\]\(([^)]+)\)', masthead)
            self.assertGreaterEqual(len(badges), 10, name)
            labels = {label for label, _, _ in badges}
            self.assertTrue({'Python', '3D Slicer', 'Qt', 'PyTorch', 'NumPy', 'SimpleITK',
                             'SlicerDMRI', 'DIPY', 'MRtrix3', 'Agent Skills', 'License'} <= labels)
            headings = {re.sub(r'[^\w\s-]', '', heading.strip().lower()).replace(' ', '-')
                        for heading in re.findall(r'^#{1,6} (.+)$', text, re.M)}
            for _, url, target in badges:
                self.assertTrue(urlsplit(url).path.startswith('/badge/'), url)
                if target.startswith('#'):
                    self.assertIn(target[1:], headings)
                elif not urlsplit(target).scheme:
                    self.assertTrue((ROOT / target).is_file(), target)
            self.assertIn('/badge/Optional-MRtrix3-', masthead)
            self.assertNotIn('/actions/workflows/', masthead)
            rendered.append([(label, url) for label, url, _ in badges])
        self.assertEqual(*rendered)

    def test_readme_bash_examples_match_across_languages(self):
        commands = [re.findall(r'```bash\n(.*?)\n```', (ROOT / name).read_text(encoding='utf-8'), re.S)
                    for name in READMES]
        self.assertEqual(*commands)
        self.assertFalse(any('--clean' in command for command in commands[0]))
        if shutil.which('bash'):
            checked = subprocess.run(['bash', '-n'], input='\n'.join(commands[0]), text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_readme_cli_example_is_a_strict_nonexecuting_dti_check(self):
        for name in READMES:
            with self.subTest(readme=name):
                text = (ROOT / name).read_text(encoding='utf-8')
                commands = re.findall(r'```bash\n(.*?)\n```', text, re.S)
                code = next(code for code in commands if '--launch PythonSlicer' in code)
                code = '\n'.join(line for line in code.splitlines() if not line.startswith('export '))
                tokens = shlex.split(code.replace('\\\n', ' '))
                self.assertEqual(tokens[1:4], ['--launch', 'PythonSlicer', 'shared/run_subject_pipeline_cli.py'])
                args = build_parser().parse_args(tokens[4:])
                self.assertTrue(args.doctor)
                self.assertFalse(args.execute)
                self.assertTrue(args.no_user_config and args.strict_environment)
                self.assertEqual(args.brain_mask_backend, 'provided')
                self.assertEqual(resolve_analysis_options(args), ('validation', 'microstructure'))
