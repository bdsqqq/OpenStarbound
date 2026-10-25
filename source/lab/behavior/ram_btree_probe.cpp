#include "StarBTreeLab.hpp"
#include "StarBTreeDatabase.hpp"
#include "StarEncode.hpp"
#include "StarJson.hpp"
#include <array>
#include <iostream>
#include <limits>
using namespace Star;
static void require(bool x) { if (!x) throw StarException("probe assertion"); }
static Json probe(char fill, bool sha) {
  auto b = make_shared<BehaviorBTreeBuffer>(fill);
  require(b->size() == 0);
  BTreeSha256Database db(sha ? "behavior_sha256" : "behavior_vlq");
  db.setIODevice(b); db.setBlockSize(512);
  if (!sha) db.setAutoCommit(false);
  require(db.autoCommit() == sha); require(db.open());
  JsonArray found;
  ByteArray pages;
  if (sha) {
    String key = "behaviorlab-sha256-key";
    ByteArray initial("alpha\0one", 9), updated("beta\0two", 8);
    require(!db.insert(key, initial)); auto a = db.find(key); require(a && *a == initial);
    found.append(hexEncode(*a)); require(db.insert(key, updated));
    auto u = db.find(key); require(u && *u == updated); found.append(hexEncode(*u));
    db.commit(); db.close();
    BTreeSha256Database reopened("behavior_sha256"); reopened.setIODevice(b); reopened.setBlockSize(512);
    require(!reopened.open()); auto r = reopened.find(key); require(r && *r == updated);
    found.append(hexEncode(*r)); require(reopened.remove(key)); require(!reopened.contains(key));
    require(reopened.recordCount() == 0); reopened.close(); pages = b->data();
  } else {
    std::array<String, 3> const keys{"vlq-a", "vlq-b", "vlq-c"};
    std::array<size_t, 3> const lengths{127, 128, 700};
    std::array<ByteArray, 3> values;
    for (size_t seed=0; seed<3; ++seed) {
      values[seed].resize(lengths[seed]);
      for (size_t i=0; i<lengths[seed]; ++i) values[seed][i]=static_cast<char>((i+seed)&255);
    }
    for (size_t i=0; i<3; ++i) require(!db.insert(keys[i], values[i]));
    db.commit(); pages=b->data(); db.close(false);
    BTreeSha256Database reopened("behavior_vlq"); reopened.setIODevice(b); reopened.setBlockSize(512);
    require(!reopened.open());
    for (size_t i=0; i<3; ++i) { auto r=reopened.find(keys[i]); require(r && *r==values[i]); found.append(hexEncode(*r)); }
    reopened.close(false);
  }
  return JsonObject{{"found",found},{"pagesHex",hexEncode(pages)}};
}
static unsigned guards() {
  BehaviorBTreeBuffer b(char(0xa5)); b.resize(8192); unsigned n=0;
  auto check=[&](auto fn) { auto bytes=b.data(); auto size=b.size(); auto ptr=b.ptr(); bool caught=false;
    try { fn(); } catch (StarException const&) { caught=true; }
    require(caught && b.size()==size && b.data()==bytes && b.ptr()==ptr); ++n; };
  char c='x';
  check([&]{b.resize(-1);}); check([&]{b.resize(8193);});
  check([&]{b.writeAbsolute(8192,&c,1);}); check([&]{b.writeAbsolute(-1,&c,1);});
  b.seek(-1); check([&]{b.write(&c,1);});
  b.seek(0); check([&]{b.write(&c,std::numeric_limits<size_t>::max());});
  check([&]{b.writeAbsolute(8191,&c,2);});
  return n;
}
int main(int argc,char**) {
  try { char fill=argc>1 ? char(0xa5) : 0;
    Json result=JsonObject{{"sha",probe(fill,true)},{"vlq",probe(fill,false)},{"bytes",probe(fill,false)},{"guards",guards()}};
    std::cout << result.printJson().utf8() << '\n'; return 0;
  } catch (std::exception const& e) { std::cerr << e.what() << '\n'; return 1; }
}
