"""Generate only prototype wrappers; source-map order is the mode contract."""
from pathlib import Path
import json
H=Path(__file__).resolve().parent
S=H.parent
rows=json.loads((S/'source-map.json').read_text())['StarFile.cpp']
original=(S/'StarFile.original.cpp').read_text().splitlines(True)
bodies={}
def body(m,locals,ops,ret=''):
    cases='\n'.join(f'case {i}: {{ {op} }}' for i,op in enumerate(ops))
    bodies[m]=f'''{locals}
  FilePrototype::invoke({m}, {len(ops)}, [&](uint32_t op, [[maybe_unused]] uint64_t a)->uint64_t {{
    switch(op) {{\n{cases}\n    }}
    throw std::logic_error("invalid leaf");
  }});
  {ret}
'''
def s(x):return x+'; return 0;'
def v(x):return 'return '+x+';'
body(0,'auto parent=dirName(fileName);', [v('isDirectory(parent)'),s('makeDirectoryRecursive(parent)'),v('isDirectory(fileName)'),s('makeDirectory(fileName)')])
body(1,'''struct Traversal {
 String fileInDir; bool isDir;
 List<pair<String,bool>> entries;
 decltype(entries.begin()) it;
 Traversal(String const& name):entries(dirList(name)),it(entries.begin()){}
};
std::optional<Traversal> traversal;''',[s('traversal.emplace(fileName)'),v('traversal->it!=traversal->entries.end()'),s('std::tie(traversal->fileInDir,traversal->isDir)=*traversal->it; traversal->fileInDir=relativeTo(fileName,traversal->fileInDir)'),v('traversal->isDir'),s('removeDirectoryRecursive(traversal->fileInDir)'),s('remove(traversal->fileInDir)'),s('++traversal->it'),s('traversal.reset()'),s('remove(fileName)')])
body(2,'auto sourceFile=File::open(source,IOMode::Read); auto targetFile=File::open(target,IOMode::ReadWrite); char buf[1024]; size_t r=0;', [s('targetFile->resize(0)'),v('sourceFile->atEnd()'),s('r=sourceFile->read(buf,1024)'),s('targetFile->writeFull(buf,r)')])
body(3,'auto file=make_shared<File>(filename);',[s('file->open(mode)')],'return file;')
body(4,'FilePtr file=File::open(filename,IOMode::Read); ByteArray bytes; char buffer[1024];',[v('file->atEnd()'),v('file->read(buffer,1024)'),s('bytes.append(buffer,a)')],'return bytes;')
body(5,'FilePtr file=File::open(filename,IOMode::Read); std::string str; char buffer[1024];',[v('file->atEnd()'),v('file->read(buffer,1024)'),s('str.push_back(buffer[a])')],'return str;')
body(6,'StreamOffset result;',[s('result=File::open(filename,IOMode::Read)->size()')],'return result;')
body(7,'FilePtr file=File::open(filename,IOMode::Write|IOMode::Truncate);',[s('file->writeFull(data,len)')])
for m,expr in [(8,'writeFile(data.ptr(),data.size(),filename)'),(9,'writeFile(data.utf8Ptr(),data.utf8Size(),filename)'),(10,'overwriteFileWithRename(data.ptr(),data.size(),filename,newSuffix)'),(11,'overwriteFileWithRename(data.utf8Ptr(),data.utf8Size(),filename,newSuffix)')]:body(m,'',[s(expr)])
body(12,'''struct Iteration {
 String const& sourceFile; String curExtension; String nextExtension;
 Iteration(String const& initialFile,String const& targetFile,String const& prefix,unsigned i):
 sourceFile(i==1?initialFile:targetFile),curExtension(i==1?"":strf("{}{}",prefix,i-1)),nextExtension(strf("{}{}",prefix,i)){}
}; std::optional<Iteration> iteration;''',[v('maximumBackups'),s('iteration.emplace(initialFile,targetFile,backupExtensionPrefix,static_cast<unsigned>(a))'),v('File::isFile(iteration->sourceFile+iteration->curExtension)'),s('File::copy(iteration->sourceFile+iteration->curExtension,targetFile+iteration->nextExtension)'),s('iteration.reset()')])
body(13,'',[s('backupFileInSequence(targetFile,targetFile,maximumBackups,backupExtensionPrefix)')])
body(14,'',[s('m_file=0')]);body(15,'',['return 0;']);body(16,'',[s('close()')])
for m,kind,expr in [(17,'pos','result=ftell(m_file)'),(18,'seek','fseek(m_file,offset,seekMode)'),(20,'eof','result=ftell(m_file)>=fsize(m_file)'),(29,'sync','fsync(m_file)')]:
 body(m,('bool result;' if m==20 else 'StreamOffset result;') if m in (17,20) else '',[v('bool(m_file)'),f'throw IOException("{kind} called on closed File");',s(expr)],'return result;' if m in (17,20) else '')
body(19,'StreamOffset result;',[s('result=fsize(m_file)')],'return result;')
for m,kind,guard,raw in [(21,'read','isReadable()','fread'),(22,'write','isWritable()','fwrite')]:
 body(m,'size_t result;',[v('bool(m_file)'),f'throw IOException("{kind} called on closed File");',v(guard),f'throw IOException("{kind} called on non-{ "readable" if m==21 else "writable"} File");',s(f'result={raw}(m_file,data,len)')],'return result;')
for m,raw,pos in [(23,'pread','readPosition'),(24,'pwrite','writePosition')]:body(m,'size_t result;',[s(f'result={raw}(m_file,data,len,{pos})')],'return result;')
body(25,'',['return 0;'],'return m_filename;')
body(26,'',[v('isOpen()'),'throw IOException("Cannot call setFilename while File is open");',s('m_filename=std::move(filename)')])
body(27,'',[s('close()'),v('m_filename.empty()'),'throw IOException("Cannot remove file, no filename set");',s('remove(m_filename)')])
body(28,'',[v('isOpen()'),s('open(mode())'),s('File::resize(m_file,s)'),s('close()')])
body(30,'',[s('close()'),v('m_filename.empty()'),'throw IOException("Cannot open file, no filename set");',s('m_file=fopen(m_filename.utf8Ptr(),m)'),s('setMode(m)')])
body(31,'',[v('bool(m_file)'),s('fclose(m_file)'),s('m_file=0'),s('setMode(IOMode::Closed)')])
body(32,'bool unnamed=false;',[v('m_filename.empty()'),s('unnamed=true'),s('unnamed=false')],'if(unnamed) return "<unnamed temp file>"; else return m_filename;')
body(33,'auto cloned=make_shared<File>(m_filename);',[v('isOpen()'),s('cloned->open(mode())'),s('cloned->seek(pos())')],'return cloned;')
out=['#include "StarFile.hpp"\n#include "StarFormat.hpp"\n#include "native.hpp"\n#include <optional>\nnamespace Star {\n']
for m,row in enumerate(rows):
 text=''.join(original[row['line']-1:row['endLine']]);prefix=text[:text.index('{')+1]
 out.append(f'// source-map mode {m}; original lines {row["line"]}-{row["endLine"]}\n'+prefix+'\n'+bodies[m]+'}\n')
out.append('}\n')
rendered='\n'.join(line.rstrip() for line in ''.join(out).splitlines())+'\n'
if __name__=='__main__':
 import sys
 if '--check' in sys.argv:
  if (H/'wrappers.cpp').read_text()!=rendered:raise SystemExit('wrapper drift')
 else:(H/'wrappers.cpp').write_text(rendered)
