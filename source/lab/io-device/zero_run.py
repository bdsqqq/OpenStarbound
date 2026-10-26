"""Supplemental native null/zero observation; never a full-calibration pass."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'source/lab/behavior'));import build_provenance
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 out=ROOT/'build/io-device-lab/oracle-null-r1'
 if out.exists():raise ValueError('fresh output required')
 out.mkdir();native=ROOT/'build/behavior/reference/bin/starbound';before=build_provenance.verify(native)
 baseline=ROOT/'build/io-device-lab/oracle-r2';receipts=json.loads((baseline/'receipts.json').read_text());cmd=next(x['command'] for x in receipts if x['name']=='current-compile')
 exe=out/'zero';cmd=[str(HERE/'zero.cpp') if x==str(HERE/'lab.cpp') else str(exe) if x==str(baseline/'current') else '-Wl,-map,'+str(out/'zero.map') if x.startswith('-Wl,-map,') else x for x in cmd]
 binds={str(p):sha(p) for p in [HERE/'zero.cpp',HERE/'zero_run.py',ROOT/'source/core/StarIODevice.cpp',ROOT/'source/core/StarIODevice.hpp',baseline/'native-core.a',Path(cmd[0]),Path(sys.executable).resolve()]}
 records=[]
 for name,command in [('compile',cmd),('execute',[str(exe)])]:
  r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60);(out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr);records.append(dict(command=command,returncode=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()));assert r.returncode==0
 assert r.stdout==b'r/1/0;w/1/0;r/0/0;w/0/0;w/1/0;\n'
 assert all(sha(p)==h for p,h in binds.items());assert build_provenance.verify(native)==before
 (out/'report.json').write_text(json.dumps(dict(status='FINITE_NATIVE_NULL_ZERO_OBSERVATION',bindings=binds,receipts=records,binary_sha256=sha(exe),native_closure=before,limits='supplemental only; no full-corpus qualification or Rust/game claim'),indent=2)+'\n')
 print(r.stdout.decode().strip())
if __name__=='__main__':main()
