#include "native.hpp"
#include <thread>
#include <iostream>
#include <limits>
static uint32_t throws(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*){throw 73;}
int main(){
 auto need=[](bool b){if(!b)throw std::runtime_error("protocol check");};
 int dummy=0;need(file_host_run(34,&dummy,throws)==2);need(file_host_run(0,nullptr,throws)==2);need(file_host_run(0,&dummy,nullptr)==2);
 need(file_host_run(15,&dummy,throws)==3);
 auto token=std::make_exception_ptr(42);bool same=false;
 try{FilePrototype::invoke(15,1,[&](uint32_t,uint64_t)->uint64_t{std::rethrow_exception(token);});}catch(...){same=std::current_exception()==token;}need(same);
 FilePrototype::invoke(15,1,[&](uint32_t,uint64_t){FilePrototype::invoke(15,1,[](uint32_t,uint64_t){return uint64_t(0);});return uint64_t(0);});
 auto leaf=[](void*,uint32_t,uint64_t){return uint64_t(91);};
 FilePrototype::Context ctx(&dummy,leaf,1,sizeof(dummy));uint64_t out=13;
 need(FilePrototype::host(&dummy,0,0,0,0,&out)==2&&out==13);
 need(FilePrototype::host(&ctx,1,0,0,0,&out)==2&&out==13);
 need(FilePrototype::host(&ctx,0,0,0,0,nullptr)==2);
 alignas(uint64_t) unsigned char storage[24]{};
 need(FilePrototype::host(&ctx,0,0,0,0,reinterpret_cast<uint64_t*>(storage+1))==2);
 need(FilePrototype::host(&ctx,0,0,0,0,reinterpret_cast<uint64_t*>(std::numeric_limits<uintptr_t>::max()-7))==2);
 for(auto byte:storage)need(byte==0);
 need(FilePrototype::host(&ctx,0,0,0,0,reinterpret_cast<uint64_t*>(&ctx))==2);
 need(FilePrototype::host(&ctx,0,0,0,0,&out)==0&&out==91);
 uint64_t parent=file_host_count(15,0);
 std::thread thread([&]{need(file_host_count(15,0)==0);FilePrototype::invoke(15,1,[](uint32_t,uint64_t){return uint64_t(0);});need(file_host_count(15,0)==1);});thread.join();need(file_host_count(15,0)==parent);
 for(unsigned m=0;m<34;++m)need(file_host_count(m,0)==file_host_count(m,1)+file_host_count(m,2));
 std::cout<<"native protocol finite controls pass\n";
}
