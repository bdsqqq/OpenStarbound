import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('static_vector_configuration', HERE / 'configuration.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ConfigurationTests(unittest.TestCase):
    def flags(self):
        return ['-D' + key for key, value in config.profiles()['candidate'].items() if value == 'ON']

    def cache(self, role):
        return '\n'.join(key + ':BOOL=' + value for key, value in config.profiles()[role].items())

    def test_current_source_defaults(self):
        config.validate_source()
        self.assertEqual(len(config.SELECTORS), 30)
        self.assertEqual(len(config.configure_options('candidate')), 30)

    def test_profiles_extend_existing_policy(self):
        profiles = config.profiles()
        self.assertEqual({k for k, v in profiles['candidate'].items() if v == 'OFF'},
                         {'STAR_USE_RUST_LINE_QUERY'})
        self.assertTrue(all(v == 'OFF' for v in profiles['reference'].values()))
        for role in profiles:
            expected = dict(profiles[role])
            del expected[config.STATIC_VECTOR]
            self.assertEqual(expected, config._legacy.profiles()[role])
            config.validate_profile(role, profiles[role])
            config.validate_cache(role, self.cache(role))

    def test_supported_explicit_compiler_flags(self):
        config.validate_flags('reference', ['-O3', '-ffast-math', '-DOTHER=1'])
        config.validate_flags('candidate', ['-O3', '-ffast-math', *self.flags()])
        split = [word for key in self.flags() for word in ('-D', key[2:])]
        config.validate_flags('candidate', split)

    def test_synthetic_all_on_profile_and_macros_rejected(self):
        profile = dict(config.profiles()['candidate'], STAR_USE_RUST_LINE_QUERY='ON')
        with self.assertRaisesRegex(ValueError, 'unsupported production'):
            config.validate_profile('candidate', profile)
        with self.assertRaisesRegex(ValueError, 'supported production profile'):
            config.validate_flags('candidate', self.flags() + ['-DSTAR_USE_RUST_LINE_QUERY'])

    def test_missing_duplicate_unknown_or_undefined_macros_rejected(self):
        bad = [self.flags()[:-1], self.flags() + self.flags()[:1],
               self.flags() + ['-DSTAR_USE_RUST_FAKE'],
               self.flags() + ['-USTAR_USE_RUST_STATIC_VECTOR'],
               self.flags() + ['-U', 'STAR_USE_RUST_STATIC_VECTOR']]
        for flags in bad:
            with self.subTest(flags=flags[-2:]), self.assertRaises(ValueError):
                config.validate_flags('candidate', flags)

    def test_zero_definition_is_not_off(self):
        for flags in [['-DSTAR_USE_RUST_LINE_QUERY=0'], ['-D', 'STAR_USE_RUST_LINE_QUERY=0'],
                      ['-DSTAR_USE_RUST_STATIC_VECTOR=0']]:
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, 'bare positive'):
                config.validate_flags('reference', flags)

    def test_response_and_dangling_switches_rejected(self):
        for flags in [['@hidden.rsp'], ['-D'], ['-U']]:
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                config.validate_flags('reference', flags)

    def test_cache_must_be_complete_unique_and_supported(self):
        candidate = self.cache('candidate')
        for text in [candidate.replace('STAR_USE_RUST_LINE_QUERY:BOOL=OFF', 'STAR_USE_RUST_LINE_QUERY:BOOL=ON'),
                     candidate + '\nSTAR_USE_RUST_STATIC_VECTOR:BOOL=ON',
                     candidate.replace('STAR_USE_RUST_STATIC_VECTOR:BOOL=ON', ''),
                     candidate.replace('STAR_USE_RUST_STATIC_VECTOR', 'STAR_USE_RUST_FAKE'),
                     candidate + '\nSTAR_USE_RUST_FAKE:STRING=ON',
                     candidate.replace('STAR_USE_RUST_STATIC_VECTOR:BOOL', 'STAR_USE_RUST_STATIC_VECTOR:STRING')]:
            with self.subTest(text=text[-80:]), self.assertRaises(ValueError):
                config.validate_cache('candidate', text)

    def test_unknown_role_rejected(self):
        for function, args in [(config.validate_profile, ({},)), (config.validate_cache, ('',)),
                               (config.validate_flags, ([],)), (config.configure_options, ())]:
            with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                function('all-on', *args)

    def test_source_default_duplicate_missing_or_unknown_mutants_rejected(self):
        text = (config.ROOT / 'source/CMakeLists.txt').read_text()
        line = next(line for line in text.splitlines(True) if line.startswith('option(STAR_USE_RUST_STATIC_VECTOR '))
        bad = [text.replace(line, line.replace('OFF)', 'ON)')), text + line,
               text.replace(line, ''), text.replace(line, line.replace('STATIC_VECTOR', 'FAKE'))]
        for mutation in bad:
            with self.subTest(size=len(mutation)), self.assertRaises(ValueError):
                config.validate_source(mutation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
