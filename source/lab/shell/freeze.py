#!/usr/bin/env python3
"""One-time snapshot creator; run.py independently checks every byte against git."""
import hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
REV='40d9189f941b1b49cd93a72cd98443824998dbc0'
result={}
for ext in ['cpp','hpp']:
 raw=subprocess.check_output(['git','show',REV+':source/core/StarShellParser.'+ext])
 (HERE/('StarShellParser.original.'+ext)).write_bytes(raw)
 adapted=raw.replace(b'namespace Star {',b'namespace ShellReference {\nusing namespace Star;')
 if ext=='cpp':adapted=adapted.replace(b'"StarShellParser.hpp"',b'"StarShellParser.reference.hpp"')
 (HERE/('StarShellParser.reference.'+ext)).write_bytes(adapted)
 result[ext]={'raw_sha256':hashlib.sha256(raw).hexdigest(),'adapted_sha256':hashlib.sha256(adapted).hexdigest()}
(HERE/'freeze.json').write_text(json.dumps({'revision':REV,'files':result},indent=2)+'\n')
