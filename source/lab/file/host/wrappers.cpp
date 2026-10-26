#include "StarFile.hpp"
#include "StarFormat.hpp"
#include "native.hpp"
#include <optional>
namespace Star {
// source-map mode 0; original lines 8-14
void File::makeDirectoryRecursive(String const& fileName) {
auto parent=dirName(fileName);
  FilePrototype::invoke(0, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return isDirectory(parent); }
case 1: { makeDirectoryRecursive(parent); return 0; }
case 2: { return isDirectory(fileName); }
case 3: { makeDirectory(fileName); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 1; original lines 16-34
void File::removeDirectoryRecursive(String const& fileName) {
struct Traversal {
 String fileInDir; bool isDir;
 List<pair<String,bool>> entries;
 decltype(entries.begin()) it;
 Traversal(String const& name):entries(dirList(name)),it(entries.begin()){}
};
std::optional<Traversal> traversal;
  FilePrototype::invoke(1, 9, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { traversal.emplace(fileName); return 0; }
case 1: { return traversal->it!=traversal->entries.end(); }
case 2: { std::tie(traversal->fileInDir,traversal->isDir)=*traversal->it; traversal->fileInDir=relativeTo(fileName,traversal->fileInDir); return 0; }
case 3: { return traversal->isDir; }
case 4: { removeDirectoryRecursive(traversal->fileInDir); return 0; }
case 5: { remove(traversal->fileInDir); return 0; }
case 6: { ++traversal->it; return 0; }
case 7: { traversal.reset(); return 0; }
case 8: { remove(fileName); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 2; original lines 36-47
void File::copy(String const& source, String const& target) {
auto sourceFile=File::open(source,IOMode::Read); auto targetFile=File::open(target,IOMode::ReadWrite); char buf[1024]; size_t r=0;
  FilePrototype::invoke(2, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { targetFile->resize(0); return 0; }
case 1: { return sourceFile->atEnd(); }
case 2: { r=sourceFile->read(buf,1024); return 0; }
case 3: { targetFile->writeFull(buf,r); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 3; original lines 49-53
FilePtr File::open(const String& filename, IOMode mode) {
auto file=make_shared<File>(filename);
  FilePrototype::invoke(3, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { file->open(mode); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return file;
}
// source-map mode 4; original lines 55-65
ByteArray File::readFile(String const& filename) {
FilePtr file=File::open(filename,IOMode::Read); ByteArray bytes; char buffer[1024];
  FilePrototype::invoke(4, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return file->atEnd(); }
case 1: { return file->read(buffer,1024); }
case 2: { bytes.append(buffer,a); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return bytes;
}
// source-map mode 5; original lines 67-78
String File::readFileString(String const& filename) {
FilePtr file=File::open(filename,IOMode::Read); std::string str; char buffer[1024];
  FilePrototype::invoke(5, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return file->atEnd(); }
case 1: { return file->read(buffer,1024); }
case 2: { str.push_back(buffer[a]); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return str;
}
// source-map mode 6; original lines 80-82
StreamOffset File::fileSize(String const& filename) {
StreamOffset result;
  FilePrototype::invoke(6, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { result=File::open(filename,IOMode::Read)->size(); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 7; original lines 84-87
void File::writeFile(char const* data, size_t len, String const& filename) {
FilePtr file=File::open(filename,IOMode::Write|IOMode::Truncate);
  FilePrototype::invoke(7, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { file->writeFull(data,len); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 8; original lines 89-91
void File::writeFile(ByteArray const& data, String const& filename) {

  FilePrototype::invoke(8, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { writeFile(data.ptr(),data.size(),filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 9; original lines 93-95
void File::writeFile(String const& data, String const& filename) {

  FilePrototype::invoke(9, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { writeFile(data.utf8Ptr(),data.utf8Size(),filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 10; original lines 97-99
void File::overwriteFileWithRename(ByteArray const& data, String const& filename, String const& newSuffix) {

  FilePrototype::invoke(10, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { overwriteFileWithRename(data.ptr(),data.size(),filename,newSuffix); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 11; original lines 101-103
void File::overwriteFileWithRename(String const& data, String const& filename, String const& newSuffix) {

  FilePrototype::invoke(11, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { overwriteFileWithRename(data.utf8Ptr(),data.utf8Size(),filename,newSuffix); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 12; original lines 105-115
void File::backupFileInSequence(String const& initialFile, String const& targetFile, unsigned maximumBackups, String const& backupExtensionPrefix) {
struct Iteration {
 String const& sourceFile; String curExtension; String nextExtension;
 Iteration(String const& initialFile,String const& targetFile,String const& prefix,unsigned i):
 sourceFile(i==1?initialFile:targetFile),curExtension(i==1?"":strf("{}{}",prefix,i-1)),nextExtension(strf("{}{}",prefix,i)){}
}; std::optional<Iteration> iteration;
  FilePrototype::invoke(12, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return maximumBackups; }
case 1: { iteration.emplace(initialFile,targetFile,backupExtensionPrefix,static_cast<unsigned>(a)); return 0; }
case 2: { return File::isFile(iteration->sourceFile+iteration->curExtension); }
case 3: { File::copy(iteration->sourceFile+iteration->curExtension,targetFile+iteration->nextExtension); return 0; }
case 4: { iteration.reset(); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 13; original lines 117-119
void File::backupFileInSequence(String const& targetFile, unsigned maximumBackups, String const& backupExtensionPrefix) {

  FilePrototype::invoke(13, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { backupFileInSequence(targetFile,targetFile,maximumBackups,backupExtensionPrefix); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 14; original lines 121-124
File::File()
  : IODevice(IOMode::Closed) {

  FilePrototype::invoke(14, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { m_file=0; return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 15; original lines 126-127
File::File(String filename)
  : IODevice(IOMode::Closed), m_filename(std::move(filename)), m_file(0) {

  FilePrototype::invoke(15, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 16; original lines 129-131
File::~File() {

  FilePrototype::invoke(16, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { close(); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 17; original lines 133-138
StreamOffset File::pos() {
StreamOffset result;
  FilePrototype::invoke(17, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("pos called on closed File"); }
case 2: { result=ftell(m_file); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 18; original lines 140-145
void File::seek(StreamOffset offset, IOSeek seekMode) {

  FilePrototype::invoke(18, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("seek called on closed File"); }
case 2: { fseek(m_file,offset,seekMode); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 19; original lines 147-149
StreamOffset File::size() {
StreamOffset result;
  FilePrototype::invoke(19, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { result=fsize(m_file); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 20; original lines 151-156
bool File::atEnd() {
bool result;
  FilePrototype::invoke(20, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("eof called on closed File"); }
case 2: { result=ftell(m_file)>=fsize(m_file); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 21; original lines 158-166
size_t File::read(char* data, size_t len) {
size_t result;
  FilePrototype::invoke(21, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("read called on closed File"); }
case 2: { return isReadable(); }
case 3: { throw IOException("read called on non-readable File"); }
case 4: { result=fread(m_file,data,len); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 22; original lines 168-176
size_t File::write(const char* data, size_t len) {
size_t result;
  FilePrototype::invoke(22, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("write called on closed File"); }
case 2: { return isWritable(); }
case 3: { throw IOException("write called on non-writable File"); }
case 4: { result=fwrite(m_file,data,len); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 23; original lines 178-180
size_t File::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
size_t result;
  FilePrototype::invoke(23, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { result=pread(m_file,data,len,readPosition); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 24; original lines 182-184
size_t File::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) {
size_t result;
  FilePrototype::invoke(24, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { result=pwrite(m_file,data,len,writePosition); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 25; original lines 186-188
String File::fileName() const {

  FilePrototype::invoke(25, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return m_filename;
}
// source-map mode 26; original lines 190-194
void File::setFilename(String filename) {

  FilePrototype::invoke(26, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return isOpen(); }
case 1: { throw IOException("Cannot call setFilename while File is open"); }
case 2: { m_filename=std::move(filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 27; original lines 196-201
void File::remove() {

  FilePrototype::invoke(27, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { close(); return 0; }
case 1: { return m_filename.empty(); }
case 2: { throw IOException("Cannot remove file, no filename set"); }
case 3: { remove(m_filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 28; original lines 203-214
void File::resize(StreamOffset s) {

  FilePrototype::invoke(28, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return isOpen(); }
case 1: { open(mode()); return 0; }
case 2: { File::resize(m_file,s); return 0; }
case 3: { close(); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 29; original lines 216-221
void File::sync() {

  FilePrototype::invoke(29, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { throw IOException("sync called on closed File"); }
case 2: { fsync(m_file); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 30; original lines 223-230
void File::open(IOMode m) {

  FilePrototype::invoke(30, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { close(); return 0; }
case 1: { return m_filename.empty(); }
case 2: { throw IOException("Cannot open file, no filename set"); }
case 3: { m_file=fopen(m_filename.utf8Ptr(),m); return 0; }
case 4: { setMode(m); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 31; original lines 232-237
void File::close() {

  FilePrototype::invoke(31, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return bool(m_file); }
case 1: { fclose(m_file); return 0; }
case 2: { m_file=0; return 0; }
case 3: { setMode(IOMode::Closed); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 32; original lines 239-244
String File::deviceName() const {
bool unnamed=false;
  FilePrototype::invoke(32, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return m_filename.empty(); }
case 1: { unnamed=true; return 0; }
case 2: { unnamed=false; return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  if(unnamed) return "<unnamed temp file>"; else return m_filename;
}
// source-map mode 33; original lines 246-255
IODevicePtr File::clone() {
auto cloned=make_shared<File>(m_filename);
  FilePrototype::invoke(33, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return isOpen(); }
case 1: { cloned->open(mode()); return 0; }
case 2: { cloned->seek(pos()); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return cloned;
}
}
