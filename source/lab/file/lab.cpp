#include "StarFile.hpp"
#include <iostream>
#include <exception>
using namespace Star;
static void row(char const* key, long long value) { std::cout << key << '\t' << value << '\n'; }
template<class F> void fails(char const* key,F f) { try { f(); row(key,0); } catch(IOException const&) { row(key,1); } }
struct Probe : File {
  using File::File;
  int closes=0, opens=0, positions=0;
  bool throwClose=false;
  std::exception_ptr token=std::make_exception_ptr(42);
  void close() override { ++closes; auto name=fileName(); if(throwClose)std::rethrow_exception(token); File::close(); }
  void open(IOMode m) override { ++opens; File::open(m); }
  StreamOffset pos() override { ++positions; return File::pos(); }
};
int main(int argc,char**argv) {
 if(argc!=2)return 2;
 String root(argv[1]); auto path=[&](char const*n){return root+"/"+n;};
 File f;
 row("default-mode",int(f.mode())); row("default-name",f.fileName().empty()); row("default-device",f.deviceName()=="<unnamed temp file>");
 // stdin is an owned pipe supplied by the runner, so null native handle -> fd0 is nonseekable.
 char b='Q'; row("closed-size",f.size()); row("closed-pread",f.readAbsolute(0,&b,1)==size_t(-1)); row("closed-pwrite",f.writeAbsolute(0,&b,1)==size_t(-1)); row("closed-output",b=='Q');
 fails("closed-pos",[&]{f.pos();}); fails("closed-seek",[&]{f.seek(0);}); fails("closed-eof",[&]{f.atEnd();}); fails("closed-read",[&]{f.read(&b,0);}); fails("closed-write",[&]{f.write(&b,0);}); fails("closed-sync",[&]{f.sync();}); fails("empty-open",[&]{f.open(IOMode::Read);}); fails("empty-remove",[&]{f.remove();});
 f.setFilename(path("missing")); fails("missing-remove",[&]{f.remove();}); fails("missing-recursive",[&]{File::removeDirectoryRecursive(path("missing-dir"));});
 row("closed-clone",f.clone()->mode()==IOMode::Closed);
 File::makeDirectoryRecursive(path("dirs/a/b")); File::makeDirectoryRecursive(path("dirs/a/b")); row("mkdir",File::isDirectory(path("dirs/a/b")));
 for(int n : {0,1,1023,1024,1025,2049}) {
  auto p=root+"/n"+std::to_string(n); auto target=p+".copy";
  auto data=File::readFile(p); row("read-size",data.size()); row("string-size",File::readFileString(p).utf8Size()); row("file-size",File::fileSize(p));
  File::copy(p,target); row("copy-size",File::fileSize(target));
  auto h=File::open(p,IOMode::ReadWrite); row("open-pos",h->pos()); row("initial-eof",h->atEnd()); h->seek(0,IOSeek::End); row("end-pos",h->pos()); row("end-eof",h->atEnd());
  h->seek(0); row("zero-read",h->read(&b,0)); row("zero-write",h->write(&b,0));
  if(n) { h->seek(1); row("pread-count",h->readAbsolute(0,&b,1)); row("pread-pos",h->pos()); row("pwrite-count",h->writeAbsolute(0,"Z",1)); row("pwrite-pos",h->pos()); }
  h->sync(); auto c=h->clone(); row("clone-pos",c->pos()); row("clone-size",c->size()); h->resize(0); row("resize-size",h->size()); h->close(); row("close-mode",int(h->mode())); h->close();
 }
 File::copy(path("same"),path("same")); row("same-copy",File::fileSize(path("same")));
 File::writeFile("A\0B",3,path("raw")); File::writeFile(ByteArray("C\0D",3),path("bytes")); File::writeFile(String(std::string("E\0F",3)),path("text"));
 File::overwriteFileWithRename(ByteArray("G\0H",3),path("rename-bytes"),".tmp"); File::overwriteFileWithRename(String("UTF8\xc3\xa9"),path("rename-string"),".new");
 File::backupFileInSequence(path("initial"),path("backup"),3,".b"); File::backupFileInSequence(path("self-backup"),2); File::backupFileInSequence(path("initial"),path("zero-backup"),0);
 Probe p(path("probe")); p.open(IOMode::ReadWrite); row("virtual-close-open",p.closes); fails("set-open",[&]{p.setFilename(path("other"));}); row("named-device",p.deviceName()==p.fileName()); p.seek(1); auto pc=p.clone(); row("virtual-pos-clone",p.positions); row("probe-clone-pos",pc->pos());
 p.throwClose=true; try {p.File::open(IOMode::Read);} catch(...) {row("open-token",std::current_exception()==p.token);} try {p.remove();} catch(...) {row("remove-token",std::current_exception()==p.token);} row("failed-close-mode",int(p.mode())); p.throwClose=false; p.close();
 Probe closed(path("closed-resize")); fails("closed-resize",[&]{closed.resize(0);}); row("resize-open-dispatch",closed.opens); row("resize-mode",int(closed.mode())); row("resize-handle-pos",closed.pos()); closed.close();
 Probe trunc(path("trunc-clone")); trunc.open(IOMode::ReadWrite|IOMode::Truncate); trunc.write("ABC",3); trunc.seek(2); auto tc=trunc.clone(); row("truncate-clone-size",trunc.size()); row("truncate-clone-pos",tc->pos()); row("truncate-source-poscalls",trunc.positions);
 return 0;
}
