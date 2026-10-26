#include "StarFile.hpp"
#include <iostream>
using namespace Star;
void hex(char const* p,size_t n){char const*h="0123456789abcdef";for(size_t i=0;i<n;++i){unsigned char c=p[i];std::cout<<h[c>>4]<<h[c&15];}std::cout<<'\n';}
struct Reenter:File { using File::File; File* other;int* calls;void close()override{++*calls;std::cout<<"close:"<<other->fileName().utf8()<<":"<<fileName().empty()<<'\n';File::close();} };
int main(int argc,char**argv){if(argc!=2)return 2;String r(argv[1]);
 for(int n:{0,1,1023,1024,1025,2049}){String p=r+"/n"+std::to_string(n);auto b=File::readFile(p);hex(b.ptr(),b.size());auto s=File::readFileString(p);hex(s.utf8Ptr(),s.utf8Size());}
 File other("other");int calls=0;{Reenter f(r+"/reentry");f.other=&other;f.calls=&calls;f.open(IOMode::ReadWrite);std::cout<<"open:"<<calls<<'\n';}std::cout<<"destroy:"<<calls<<'\n';
 try{File::backupFileInSequence(r+"/initial",r+"/backup",3,".b");std::cout<<"backup:0\n";}catch(IOException const&){std::cout<<"backup:1\n";}
 File f(r+"/n1");f.open(IOMode::Read);char b='Q';try{f.write(&b,0);std::cout<<"write:0\n";}catch(IOException const&){std::cout<<"write:1\n";}std::cout<<"absolute:"<<(f.writeAbsolute(0,&b,1)==size_t(-1))<<'\n';f.close();f.open(IOMode::Write);try{f.read(&b,0);std::cout<<"read:0\n";}catch(IOException const&){std::cout<<"read:1\n";}return 0;}
