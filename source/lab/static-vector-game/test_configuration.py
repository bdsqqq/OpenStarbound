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
        values = dict(config.profiles()[role], **{config.BIMAP: 'OFF', config.UUID: 'OFF', config.ORDERED_SET: 'OFF', config.SET: 'OFF', config.FLAT_HASH_TABLE: 'OFF', config.MAP: 'OFF', config.PERIODIC: 'OFF', config.WORKER_POOL: 'OFF', config.TIME: 'OFF', config.NET_SIGNAL: 'OFF', config.NET_FIELD: 'OFF', config.NET_GROUP: 'OFF', config.NET_DYNAMIC: 'OFF'})
        return '\n'.join(key + ':BOOL=' + value for key, value in values.items())

    def test_current_source_defaults(self):
        config.validate_source()
        self.assertEqual(len(config.SELECTORS), 30)
        for role in config.profiles():
            self.assertEqual(len(config.CURRENT_SELECTORS), 43)
            self.assertEqual(len(config.configure_options(role)), len(config.CURRENT_SELECTORS))
            self.assertIn('-DSTAR_USE_RUST_BIMAP=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_UUID=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_ORDERED_SET=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_SET=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_FLAT_HASH_TABLE=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_MAP=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_PERIODIC=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_WORKER_POOL=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_TIME=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_NET_SIGNAL=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_NET_FIELD=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_NET_GROUP=OFF', config.configure_options(role))
            self.assertIn('-DSTAR_USE_RUST_NET_DYNAMIC=OFF', config.configure_options(role))

    def test_profiles_extend_existing_policy(self):
        profiles = config.profiles()
        self.assertEqual(len(profiles['candidate']), 30)
        self.assertEqual(sum(v == 'ON' for v in profiles['candidate'].values()), 29)
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
               self.flags() + ['-DSTAR_USE_RUST_BIMAP'],
               self.flags() + ['-DSTAR_USE_RUST_FLAT_HASH_TABLE'],
               self.flags() + ['-DSTAR_USE_RUST_MAP'],
               self.flags() + ['-DSTAR_USE_RUST_PERIODIC'],
               self.flags() + ['-DSTAR_USE_RUST_WORKER_POOL'],
               self.flags() + ['-DSTAR_USE_RUST_TIME'],
               self.flags() + ['-DSTAR_USE_RUST_NET_SIGNAL'],
               self.flags() + ['-DSTAR_USE_RUST_NET_FIELD'],
               self.flags() + ['-DSTAR_USE_RUST_NET_GROUP'],
               self.flags() + ['-DSTAR_USE_RUST_NET_DYNAMIC'],
               self.flags() + ['-DSTAR_USE_RUST_SET'],
               self.flags() + ['-DSTAR_USE_RUST_ORDERED_SET'],
               self.flags() + ['-DSTAR_USE_RUST_UUID'],
               self.flags() + ['-DSTAR_USE_RUST_UUID', '-DSTAR_USE_RUST_UUID'],
               self.flags() + ['-USTAR_USE_RUST_STATIC_VECTOR'],
               self.flags() + ['-U', 'STAR_USE_RUST_STATIC_VECTOR']]
        for flags in bad:
            with self.subTest(flags=flags[-2:]), self.assertRaises(ValueError):
                config.validate_flags('candidate', flags)

    def test_zero_definition_is_not_off(self):
        for flags in [['-DSTAR_USE_RUST_LINE_QUERY=0'], ['-D', 'STAR_USE_RUST_LINE_QUERY=0'],
                      ['-DSTAR_USE_RUST_STATIC_VECTOR=0'], ['-DSTAR_USE_RUST_MAP=0'], ['-DSTAR_USE_RUST_PERIODIC=0'], ['-DSTAR_USE_RUST_WORKER_POOL=0'], ['-DSTAR_USE_RUST_TIME=0'], ['-DSTAR_USE_RUST_NET_SIGNAL=0'], ['-DSTAR_USE_RUST_NET_FIELD=0'], ['-DSTAR_USE_RUST_NET_GROUP=0'], ['-DSTAR_USE_RUST_NET_DYNAMIC=0'], ['-DSTAR_USE_RUST_FLAT_HASH_TABLE=0'], ['-DSTAR_USE_RUST_SET=0'], ['-DSTAR_USE_RUST_ORDERED_SET=0'], ['-DSTAR_USE_RUST_UUID=0']]:
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
                     candidate.replace('STAR_USE_RUST_BIMAP:BOOL=OFF', 'STAR_USE_RUST_BIMAP:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_BIMAP:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_BIMAP:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_STATIC_VECTOR:BOOL=ON', 'STAR_USE_RUST_BIMAP:BOOL=OFF'),
                     candidate.replace('STAR_USE_RUST_BIMAP', 'STAR_USE_RUST_FAKE'),
                     candidate.replace('STAR_USE_RUST_FLAT_HASH_TABLE:BOOL=OFF', 'STAR_USE_RUST_FLAT_HASH_TABLE:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_FLAT_HASH_TABLE:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_FLAT_HASH_TABLE:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_MAP:BOOL=OFF', 'STAR_USE_RUST_MAP:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_MAP:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_MAP:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_PERIODIC:BOOL=OFF', 'STAR_USE_RUST_PERIODIC:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_PERIODIC:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_PERIODIC:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_WORKER_POOL:BOOL=OFF', 'STAR_USE_RUST_WORKER_POOL:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_WORKER_POOL:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_WORKER_POOL:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_TIME:BOOL=OFF', 'STAR_USE_RUST_TIME:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_TIME:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_TIME:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_NET_SIGNAL:BOOL=OFF', 'STAR_USE_RUST_NET_SIGNAL:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_NET_SIGNAL:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_NET_SIGNAL:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_NET_FIELD:BOOL=OFF', 'STAR_USE_RUST_NET_FIELD:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_NET_FIELD:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_NET_FIELD:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_NET_GROUP:BOOL=OFF', 'STAR_USE_RUST_NET_GROUP:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_NET_GROUP:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_NET_GROUP:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_NET_DYNAMIC:BOOL=OFF', 'STAR_USE_RUST_NET_DYNAMIC:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_NET_DYNAMIC:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_NET_DYNAMIC:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_SET:BOOL=OFF', 'STAR_USE_RUST_SET:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_SET:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_SET:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_ORDERED_SET:BOOL=OFF', 'STAR_USE_RUST_ORDERED_SET:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_ORDERED_SET:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_ORDERED_SET:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_UUID:BOOL=OFF', 'STAR_USE_RUST_UUID:BOOL=ON'),
                     candidate.replace('STAR_USE_RUST_UUID:BOOL=OFF', ''),
                     candidate + '\nSTAR_USE_RUST_UUID:BOOL=OFF',
                     candidate.replace('STAR_USE_RUST_STATIC_VECTOR:BOOL=ON', 'STAR_USE_RUST_UUID:BOOL=OFF'),
                     candidate.replace('STAR_USE_RUST_UUID', 'STAR_USE_RUST_FAKE'),
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
        for selector in (config.STATIC_VECTOR, config.BIMAP, config.UUID, config.ORDERED_SET, config.SET, config.FLAT_HASH_TABLE, config.MAP, config.PERIODIC, config.WORKER_POOL, config.TIME, config.NET_SIGNAL, config.NET_FIELD, config.NET_GROUP, config.NET_DYNAMIC):
            line = next(line for line in text.splitlines(True) if line.startswith('option(' + selector + ' '))
            bad = [text.replace(line, line.replace('OFF)', 'ON)')), text + line,
                   text.replace(line, ''), text.replace(line, line.replace(selector, 'STAR_USE_RUST_FAKE'))]
            for mutation in bad:
                with self.subTest(selector=selector, size=len(mutation)), self.assertRaises(ValueError):
                    config.validate_source(mutation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
