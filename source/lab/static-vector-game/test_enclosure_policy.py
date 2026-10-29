"""Pure profile/binding controls; no sandbox/tool/image process invocation."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('_sv_policy_test', Path(__file__).with_name('enclosure_policy.py'))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
G = Path(__file__).resolve().parents[3] / 'build/behavior/static-vector-combined-r1'


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=G)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mount = self.root / 'products'
        self.mount.mkdir()
        self.owner = dict(root=str(self.root), mount=dict(path=str(self.mount), st_dev=123),
                          device='/dev/disk41', volumeDevice='/dev/disk41s1')
        self.tool = dict(path=policy.TOOL, sha256='a' * 64, size=123)

    def test_exact_profile_utf8_and_injection_escaping(self):
        for control in ('\x01', '\x10', '\u0085'):
            with self.assertRaises(ValueError):
                policy.profile(str(self.root / ('snow-' + control)))
        mount = self.root / 'snow-☃'
        mount.mkdir()
        text = policy.profile(str(mount))
        self.assertIn(str(mount), text)
        quoted = self.root / 'snow-☃"\\)(allow file-write* (subpath "'
        quoted.mkdir()
        text = policy.profile(str(quoted))
        literal = str(quoted).replace('\\', '\\\\').replace('"', '\\"')
        self.assertEqual(text, '(version 1)(allow default)(deny file-mount file-unmount)(deny file-write*)(allow file-write* (subpath "' + literal + '"))')
        text.encode('utf-8')

    def test_noncanonical_controls_alias_and_missing_paths(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.mount)
        file = self.root / 'file'
        file.write_text('tiny fixture')
        for value in ('', '/', 'relative', True, 1.0, str(alias), str(file),
                      str(self.mount) + '/', str(self.root) + '/./products',
                      str(self.root) + '/products/../products', str(self.root / 'missing'),
                      str(self.mount) + '\x00', str(self.mount) + '\n', str(self.mount) + '\x7f'):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError, OSError)):
                policy.profile(value)

    def test_binding_strict_types_exact_profile_and_tool(self):
        bound = policy.binding(self.owner, self.tool)
        self.assertEqual(bound['profile'], policy.profile(str(self.mount)))
        self.assertEqual(bound['mount'], self.owner['mount'])
        for key, value in (('path', '/other'), ('size', True), ('size', 123.0), ('sha256', 'x')):
            tool = dict(self.tool, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                policy.binding(self.owner, tool)
        for value in (True, 123.0, 0):
            owner = copy.deepcopy(self.owner)
            owner['mount']['st_dev'] = value
            with self.assertRaises(ValueError):
                policy.binding(owner, self.tool)
        self.assertFalse(policy.same(bound, dict(bound, version=True)))
        self.assertFalse(policy.same(bound, dict(bound, version=float(policy.VERSION))))

    def test_single_wrapper_and_invalid_commands(self):
        mount = str(self.mount)
        argv = ['/python', 'provenance.py', 'begin']
        wrapped = policy.wrap(mount, argv)
        self.assertEqual(wrapped[3:], argv)
        self.assertEqual(policy.validate_command(mount, wrapped), wrapped)
        for command in ([], '', ['/a', '\x00'], [True], ['/a', 1.0], wrapped,
                        ['/a', policy.TOOL], ['/other/sandbox-exec', '-p', '(allow default)']):
            with self.subTest(command=command), self.assertRaises(ValueError):
                policy.wrap(mount, command)
        for command in (argv, [*wrapped[:1], '-f', *wrapped[2:]],
                        ['/other', *wrapped[1:]], [policy.TOOL, '-p', '(allow default)', *argv],
                        [*wrapped[:3], *wrapped], [*wrapped[:3], '/a', '\x00']):
            with self.subTest(command=command), self.assertRaises(ValueError):
                policy.validate_command(mount, command)


if __name__ == '__main__':
    unittest.main()
