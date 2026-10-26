// Scope completion releases measurement, not the caller's lexical lifetime.
// This keeps direct File::readFile local initialization possible without moves.
#include "StarFileLab.hpp"
#include <iostream>
#include <limits>

using namespace Star;
namespace {
uint64_t values[34][3]{};
uint64_t read(unsigned mode, unsigned event) { return values[mode][event]; }
void need(bool value) { if (!value) throw std::logic_error("scope probe mismatch"); }
}
int main() {
  try {
    FileLab::Recorder recorder;
    recorder.reader = read;
    values[0][0] = values[0][1] = std::numeric_limits<uint64_t>::max() - 1;
    FileLab::Scope first(recorder, 0, true);
    bool refused = false;
    try { recorder.toJson("", ""); } catch (std::logic_error const&) { refused = true; }
    need(refused);
    values[0][0] += 3; values[0][1] += 3;
    first.complete(); first.complete();
    need(recorder.liveScopes == 0 && !recorder.measuring && recorder.next == 1);
    need(recorder.scopes[0].calls.values[0][0] == 3 && recorder.scopes[0].calls.values[0][1] == 3);
    for (unsigned i = 1; i < 5; ++i) {
      FileLab::Scope scope(recorder, i, true);
      scope.complete();
    }
    // first is deliberately still alive. Serialization must be outside the
    // measurement, not outside the native return value's lexical block.
    need(recorder.toJson("", "").getBool("completed"));
    FileLab::Recorder incomplete;
    { FileLab::Scope scope(incomplete, 0, true); }
    need(!incomplete.valid && incomplete.liveScopes == 0 && !incomplete.measuring);
    need(!incomplete.toJson("", "").getBool("completed"));
    FileLab::Recorder wrongThread;
    { FileLab::Scope scope(wrongThread, 0, false); scope.complete(); }
    need(!wrongThread.valid);
    std::cout << "finite File scope lifecycle controls pass\n";
    return 0;
  } catch (std::exception const& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
