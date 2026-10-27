"""Full project configuration, then the single existing Cargo aggregate target."""
from common import *
CMAKE='/nix/store/fsdy1l7x2ybpry7lrhw2m7r6w8jvp01i-cmake-4.4.4/bin/cmake'
NINJA='/nix/store/ndfr0d2nizw172ppn99n505ikpsq9727-ninja-1.13.2/bin/ninja'
CLANG='/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang'
SDK='/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk'
TOOLS=Path('/Users/bdsqqq/.rustup/toolchains/stable-aarch64-apple-darwin/bin')
CM=OUT/'sealed-cmake'
ARCHIVE=CM/'rust-engine-ffi/aarch64-apple-darwin/release/libstar_engine_ffi.a'

def stable_sources():
 paths=list((ROOT/'source/rust').rglob('*.rs'))+list((ROOT/'source/rust').rglob('Cargo.toml'))+[ROOT/'source/rust/Cargo.lock',ROOT/'source/core/StarRustTtlCache.h',ROOT/'source/CMakeLists.txt',ROOT/'source/CMakePresets.json']+list((ROOT/'cmake').rglob('*.cmake'))+list((ROOT/'triplets').rglob('*'))+list((ROOT/'toolchains').rglob('*'))
 paths += [Path(CMAKE),Path(NINJA),Path(CLANG),Path(CLANG+'++'),Path(CLANG).parent/'ld',TOOLS/'cargo',TOOLS/'rustc',Path('/usr/bin/xcrun')]
 native=ROOT/'build/ttl-cache-native-r1/inputs.json'
 paths += [native,*map(Path,json.loads(native.read_bytes()))]
 paths+=list((ROOT/'source').rglob('CMakeLists.txt'))+list((ROOT/'source').glob('vcpkg*.json'))
 paths+=list((ROOT/'build/macos-arm-release/vcpkg_installed').rglob('*.cmake'))
 paths+=list(Path('/Users/bdsqqq/.cache/openstarbound-vcpkg/scripts').rglob('*.cmake'))
 paths+=list(Path(CMAKE).parents[1].glob('share/cmake-*/Modules/**/*.cmake'))
 return hashes(paths)

def configured_inputs():
 paths=list(map(Path,stable_sources()))
 paths+=list((ROOT/'cmake').glob('*.cmake'))+[ROOT/'source/CMakeLists.txt',ROOT/'source/CMakePresets.json']
 paths+=[p for p in CM.rglob('*') if p.is_file() and (p.suffix in ('.cmake','.ninja','.h','.hpp') or p.name in ('CMakeCache.txt','compile_commands.json')) and 'rust-engine-ffi' not in p.parts]
 paths += [Path(CMAKE),Path(NINJA),TOOLS/'cargo',TOOLS/'rustc',HERE/'canonical.py',HERE/'common.py']
 return hashes(paths)

def verify():
 record=load(OUT/'sealed-canonical.typed')
 same(record['inputs'],configured_inputs(),'canonical configured/source inputs drift')
 need(record['archive_sha256']==sha(ARCHIVE),'canonical aggregate drift')
 need(record['build_target']=='star_rust_engine_ffi_build','sole aggregate target')
 return record

def acquire():
 need(not CM.exists() and not (OUT/'sealed-canonical.typed').exists(),'fresh compiler-sealed canonical stage only');(OUT/'home').mkdir(exist_ok=True);(OUT/'tmp').mkdir(exist_ok=True)
 args=[CMAKE,'--preset','macos-arm-release','-B',CM,'-DCMAKE_C_COMPILER='+CLANG,'-DCMAKE_CXX_COMPILER='+CLANG+'++','-DCMAKE_MAKE_PROGRAM='+NINJA,'-DCMAKE_OSX_SYSROOT='+SDK,'-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON','-DCMAKE_VERBOSE_MAKEFILE=OFF','-DBUILD_TESTING=OFF','-DSTAR_ENABLE_STEAM_INTEGRATION=OFF','-DSTAR_ENABLE_DISCORD_INTEGRATION=OFF','-DSTAR_BUILD_LIGHTING_LAB=OFF','-DSTAR_USE_RUST_LIGHTING=ON','-DVCPKG_MANIFEST_INSTALL=OFF','-DVCPKG_INSTALLED_DIR='+str(ROOT/'build/macos-arm-release/vcpkg_installed'),'-DSTAR_CARGO_EXECUTABLE='+str(TOOLS/'cargo'),'-DSTAR_RUSTC_EXECUTABLE='+str(TOOLS/'rustc'),'-DSTAR_RUNTIME_OUTPUT_DIRECTORY='+str(OUT/'unused-bin')]
 dump(OUT/'sealed-configure-source-before.typed',stable_sources())
 command('sealed-canonical-configure',args,timeout=180,cwd=ROOT/'source')
 same(load(OUT/'sealed-configure-source-before.typed'),stable_sources(),'configure participating source drift')
 inputs=configured_inputs();dump(OUT/'sealed-canonical-inputs-before.typed',inputs)
 ninja=(CM/'build.ninja').read_text()
 required=['build --manifest-path','--package star-engine-ffi --target aarch64-apple-darwin --release --locked --offline','ffi/src/ttl_cache.rs']
 for value in required:need(value in ninja,'canonical generated command missing '+value)
 command('sealed-canonical-build',[CMAKE,'--build',CM,'--target','star_rust_engine_ffi_build','--parallel','2'],timeout=300,cwd=ROOT/'source')
 same(inputs,configured_inputs(),'canonical inputs changed during build')
 dump(OUT/'sealed-canonical.typed',{'status':'FRESH_CANONICAL_AGGREGATE_BUILT','build_target':'star_rust_engine_ffi_build','inputs':inputs,'archive':str(ARCHIVE),'archive_sha256':sha(ARCHIVE),'configure_complete_before_freeze':True,'limits':'aggregate build only; bridge qualification separate'})
 verify();print('FRESH_CANONICAL_AGGREGATE_BUILT',sha(ARCHIVE),flush=True)
if __name__=='__main__':
 if sys.argv[1:]==['--verify']:verify();print('CANONICAL_READONLY_PASS')
 elif not sys.argv[1:]:acquire()
 else:raise SystemExit('usage: canonical.py [--verify]')
