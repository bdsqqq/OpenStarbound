#ifdef STAR_USE_RUST_FILE
#include "StarFile.hpp"
#include "StarFormat.hpp"
#include "StarFileHost.hpp"
#include <optional>
namespace Star {
// source-map mode 0; original lines 8-14
void File::makeDirectoryRecursive(String const& fileName) {
auto parent=dirName(fileName);
  FileRust::invoke(0, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(1, 9, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(2, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(3, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(4, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(5, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(6, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(7, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { file->writeFull(data,len); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 8; original lines 89-91
void File::writeFile(ByteArray const& data, String const& filename) {

  FileRust::invoke(8, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { writeFile(data.ptr(),data.size(),filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 9; original lines 93-95
void File::writeFile(String const& data, String const& filename) {

  FileRust::invoke(9, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { writeFile(data.utf8Ptr(),data.utf8Size(),filename); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 10; original lines 97-99
void File::overwriteFileWithRename(ByteArray const& data, String const& filename, String const& newSuffix) {

  FileRust::invoke(10, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { overwriteFileWithRename(data.ptr(),data.size(),filename,newSuffix); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 11; original lines 101-103
void File::overwriteFileWithRename(String const& data, String const& filename, String const& newSuffix) {

  FileRust::invoke(11, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(12, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(13, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { backupFileInSequence(targetFile,targetFile,maximumBackups,backupExtensionPrefix); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 14; original lines 121-124
File::File()
  : IODevice(IOMode::Closed) {

  FileRust::invoke(14, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { m_file=0; return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 15; original lines 126-127
File::File(String filename)
  : IODevice(IOMode::Closed), m_filename(std::move(filename)), m_file(0) {

  FileRust::invoke(15, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 16; original lines 129-131
File::~File() {

  FileRust::invoke(16, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { close(); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });

}
// source-map mode 17; original lines 133-138
StreamOffset File::pos() {
StreamOffset result;
  FileRust::invoke(17, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(18, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(19, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(20, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(21, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(22, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(23, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(24, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { result=pwrite(m_file,data,len,writePosition); return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return result;
}
// source-map mode 25; original lines 186-188
String File::fileName() const {

  FileRust::invoke(25, 1, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
    switch(op) {
case 0: { return 0; }
    }
    throw std::logic_error("invalid leaf");
  });
  return m_filename;
}
// source-map mode 26; original lines 190-194
void File::setFilename(String filename) {

  FileRust::invoke(26, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(27, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(28, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(29, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(30, 5, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

  FileRust::invoke(31, 4, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(32, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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
  FileRust::invoke(33, 3, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {
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

#else
#include "StarFile.hpp"
#include "StarFormat.hpp"

#include <fstream>

namespace Star {

void File::makeDirectoryRecursive(String const& fileName) {
  auto parent = dirName(fileName);
  if (!isDirectory(parent))
    makeDirectoryRecursive(parent);
  if (!isDirectory(fileName))
    makeDirectory(fileName);
}

void File::removeDirectoryRecursive(String const& fileName) {
  {
    String fileInDir;
    bool isDir;

    for (auto const& p : dirList(fileName)) {
      std::tie(fileInDir, isDir) = p;

      fileInDir = relativeTo(fileName, fileInDir);

      if (isDir)
        removeDirectoryRecursive(fileInDir);
      else
        remove(fileInDir);
    }
  }

  remove(fileName);
}

void File::copy(String const& source, String const& target) {
  auto sourceFile = File::open(source, IOMode::Read);
  auto targetFile = File::open(target, IOMode::ReadWrite);

  targetFile->resize(0);

  char buf[1024];
  while (!sourceFile->atEnd()) {
    size_t r = sourceFile->read(buf, 1024);
    targetFile->writeFull(buf, r);
  }
}

FilePtr File::open(const String& filename, IOMode mode) {
  auto file = make_shared<File>(filename);
  file->open(mode);
  return file;
}

ByteArray File::readFile(String const& filename) {
  FilePtr file = File::open(filename, IOMode::Read);
  ByteArray bytes;
  while (!file->atEnd()) {
    char buffer[1024];
    size_t r = file->read(buffer, 1024);
    bytes.append(buffer, r);
  }

  return bytes;
}

String File::readFileString(String const& filename) {
  FilePtr file = File::open(filename, IOMode::Read);
  std::string str;
  while (!file->atEnd()) {
    char buffer[1024];
    size_t r = file->read(buffer, 1024);
    for (size_t i = 0; i < r; ++i)
      str.push_back(buffer[i]);
  }

  return str;
}

StreamOffset File::fileSize(String const& filename) {
  return File::open(filename, IOMode::Read)->size();
}

void File::writeFile(char const* data, size_t len, String const& filename) {
  FilePtr file = File::open(filename, IOMode::Write | IOMode::Truncate);
  file->writeFull(data, len);
}

void File::writeFile(ByteArray const& data, String const& filename) {
  writeFile(data.ptr(), data.size(), filename);
}

void File::writeFile(String const& data, String const& filename) {
  writeFile(data.utf8Ptr(), data.utf8Size(), filename);
}

void File::overwriteFileWithRename(ByteArray const& data, String const& filename, String const& newSuffix) {
  overwriteFileWithRename(data.ptr(), data.size(), filename, newSuffix);
}

void File::overwriteFileWithRename(String const& data, String const& filename, String const& newSuffix) {
  overwriteFileWithRename(data.utf8Ptr(), data.utf8Size(), filename, newSuffix);
}

void File::backupFileInSequence(String const& initialFile, String const& targetFile, unsigned maximumBackups, String const& backupExtensionPrefix) {
  for (unsigned i = maximumBackups; i > 0; --i) {
    bool initial = i == 1;
    String const& sourceFile = initial ? initialFile : targetFile;
    String curExtension = initial ? "" : strf("{}{}", backupExtensionPrefix, i - 1);
    String nextExtension = strf("{}{}", backupExtensionPrefix, i);

    if (File::isFile(sourceFile + curExtension))
      File::copy(sourceFile + curExtension, targetFile + nextExtension);
  }
}

void File::backupFileInSequence(String const& targetFile, unsigned maximumBackups, String const& backupExtensionPrefix) {
  backupFileInSequence(targetFile, targetFile, maximumBackups, backupExtensionPrefix);
}

File::File()
  : IODevice(IOMode::Closed) {
  m_file = 0;
}

File::File(String filename)
  : IODevice(IOMode::Closed), m_filename(std::move(filename)), m_file(0) {}

File::~File() {
  close();
}

StreamOffset File::pos() {
  if (!m_file)
    throw IOException("pos called on closed File");

  return ftell(m_file);
}

void File::seek(StreamOffset offset, IOSeek seekMode) {
  if (!m_file)
    throw IOException("seek called on closed File");

  fseek(m_file, offset, seekMode);
}

StreamOffset File::size() {
  return fsize(m_file);
}

bool File::atEnd() {
  if (!m_file)
    throw IOException("eof called on closed File");

  return ftell(m_file) >= fsize(m_file);
}

size_t File::read(char* data, size_t len) {
  if (!m_file)
    throw IOException("read called on closed File");

  if (!isReadable())
    throw IOException("read called on non-readable File");

  return fread(m_file, data, len);
}

size_t File::write(const char* data, size_t len) {
  if (!m_file)
    throw IOException("write called on closed File");

  if (!isWritable())
    throw IOException("write called on non-writable File");

  return fwrite(m_file, data, len);
}

size_t File::readAbsolute(StreamOffset readPosition, char* data, size_t len) {
  return pread(m_file, data, len, readPosition);
}

size_t File::writeAbsolute(StreamOffset writePosition, char const* data, size_t len) {
  return pwrite(m_file, data, len, writePosition);
}

String File::fileName() const {
  return m_filename;
}

void File::setFilename(String filename) {
  if (isOpen())
    throw IOException("Cannot call setFilename while File is open");
  m_filename = std::move(filename);
}

void File::remove() {
  close();
  if (m_filename.empty())
    throw IOException("Cannot remove file, no filename set");
  remove(m_filename);
}

void File::resize(StreamOffset s) {
  bool tempOpen = false;
  if (!isOpen()) {
    tempOpen = true;
    open(mode());
  }

  File::resize(m_file, s);

  if (tempOpen)
    close();
}

void File::sync() {
  if (!m_file)
    throw IOException("sync called on closed File");

  fsync(m_file);
}

void File::open(IOMode m) {
  close();
  if (m_filename.empty())
    throw IOException("Cannot open file, no filename set");

  m_file = fopen(m_filename.utf8Ptr(), m);
  setMode(m);
}

void File::close() {
  if (m_file)
    fclose(m_file);
  m_file = 0;
  setMode(IOMode::Closed);
}

String File::deviceName() const {
  if (m_filename.empty())
    return "<unnamed temp file>";
  else
    return m_filename;
}

IODevicePtr File::clone() {
  auto cloned = make_shared<File>(m_filename);
  if (isOpen()) {
    // Open with same mode
    cloned->open(mode());
    // Seek to same position
    cloned->seek(pos());
  }
  return cloned;
}

}

#endif
