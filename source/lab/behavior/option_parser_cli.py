#!/usr/bin/env python3
"""Real client startup/help/error exits with owned configuration and literal stdout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import behavior_lab as lab

# Application::run emits these before calling ClientApplication::startup:
# StarMainApplication_sdl.cpp:465/476 and StarLogging.cpp:28. They are kept
# byte-for-byte, not stripped or masked. Initial C++-only acquisition exposed
# this missing upstream scope before any Rust CLI observation was accepted.
PREAMBLE = b'[Info] Application: Initializing SDL\n[Info] Application: startup...\n'
HELP = ("Command Line Usage: [-help] [-version] [-bootconfig <bootconfig>] [-logfile <logfile>] [-loglevel <level>] [-quiet] [-verbose] [-runtimeconfig]\n"
        "  -help\t- Show help text\n"
        "  -version\t- Print version info\n"
        "  -bootconfig <bootconfig>\t- Boot time configuration file, defaults to sbinit.config\n"
        "  -logfile <logfile>\t- Log to the given logfile relative to the root directory, defaults to starbound.log\n"
        "  -loglevel <level>\t- Sets the logging level (debug|info|warn|error), defaults to Info\n"
        "  -quiet\t- Do not log to stdout, defaults to false\n"
        "  -verbose\t- Log to stdout, defaults to true\n"
        "  -runtimeconfig\t- Sets the path to the runtime configuration storage file relative to root directory, defauts to starbound.config\n").encode()
ERRORS = {'unknown': "No such option '-wat'",
          'missing': "Option '-loglevel' must be followed by an argument",
          'duplicate': "Option with argument '-bootconfig' specified multiple times",
          'end-markers': 'Too many positional arguments given, expected at most 0 got 1'}


def validate(name, code, output):
    expected = HELP if name in ('help', 'help-with-error') else ('Error: ' + ERRORS[name] + '\n\n').encode() + HELP
    expected = PREAMBLE + expected
    if code != (0 if name in ('help', 'help-with-error') else 1) or output != expected:
        raise ValueError('actual client CLI literal/exit mismatch: ' + name)


def run(reference, candidate, output):
    output = lab.create_owned(output)
    # Falsify the literal verifier before using it as acceptance evidence.
    try:
        validate('help', 0, b'corrupt literal fixture')
    except ValueError:
        pass
    else:
        raise ValueError('known-bad CLI verifier fixture escaped')
    rows = []
    for backend, binary in [('cpp', reference), ('rust', candidate)]:
        identity = lab.identity(binary)
        provenance = lab.verified_build(binary)
        for name in ('help', 'help-with-error', 'unknown', 'missing', 'duplicate', 'end-markers'):
            directory = lab.create_owned(output / backend / name)
            home = lab.create_owned(directory / 'home')
            frames = lab.create_owned(directory / 'frames')
            storage = lab.create_owned(frames / 'storage')
            configuration = directory / 'scenario.json'
            boot = directory / 'sbinit.config'
            lab.dump(configuration, {'outputDirectory': str(frames), 'storageDirectory': str(storage),
                                     'scenario': 'option-parser-room', 'maxFrames': 1800, 'platformWrites': False})
            lab.dump(boot, {'assetDirectories': [], 'assetSources': [], 'storageDirectory': str(storage),
                            'logDirectory': str(storage), 'includeUGC': False,
                            'defaultConfiguration': {'optionParserProof': {'color': [48, 176, 240, 255], 'label': 'OPTIONS'}}})
            arguments = {'help': ['-help'], 'help-with-error': ['-help', '-wat'],
                         'unknown': ['-wat'], 'missing': ['-loglevel'],
                         'duplicate': ['-bootconfig', str(directory / 'unselected.config')],
                         'end-markers': ['--', '--', '-wat']}[name]
            command = [str(binary.absolute()), '-bootconfig', str(boot), *arguments]
            environment = dict(os.environ)
            for key in ('SteamAppId', 'SteamGameId', 'STAR_BEHAVIOR_LAB'):
                environment.pop(key, None)
            environment.update(STAR_BEHAVIOR_LAB=str(configuration), HOME=str(home),
                               XDG_DATA_HOME=str(home / 'data'), XDG_CONFIG_HOME=str(home / 'config'),
                               XDG_CACHE_HOME=str(home / 'cache'))
            inputs = {'boot': lab.identity(boot), 'scenario': lab.identity(configuration)}
            lab.dump(directory / 'launch.json', {'command': command, 'binary': identity,
                                                'buildProvenance': provenance, 'inputs': inputs})
            with (directory / 'stdout.log').open('xb') as stream:
                process = subprocess.Popen(command, cwd=directory, env=environment,
                                           stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = process.wait(timeout=30)
                finally:
                    lab.stop_process_group(process)
            raw = (directory / 'stdout.log').read_bytes()
            row = {'backend': backend, 'case': name, 'exitCode': code,
                   'stdoutSha256': lab.sha(directory / 'stdout.log'), 'command': command}
            lab.dump(directory / 'observed.json', row)
            if inputs != {'boot': lab.identity(boot), 'scenario': lab.identity(configuration)}:
                raise ValueError('CLI input changed')
            validate(name, code, raw)
            rows.append(row)
        if lab.identity(binary) != identity or lab.verified_build(binary) != provenance:
            raise ValueError('CLI binary/source drift')
    lab.dump(output / 'report.json', {'passed': True, 'cases': rows,
                                     'knownBadLiteralRejected': True,
                                     'limits': ['Actual client startup exits, not Universe gameplay',
                                                'No version-string projection or backend-ID masking',
                                                'No parser counter receipt claimed for early exits']})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rows = run(args.reference.absolute(), args.candidate.absolute(), args.output.absolute())
    print(json.dumps({'passed': True, 'executions': len(rows)}))


if __name__ == '__main__':
    main()
