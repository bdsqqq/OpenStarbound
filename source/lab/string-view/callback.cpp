// Source-traced legal terminal deletion; backing strings outlive every call.
#include "StarStringView.hpp"
#include <exception>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
using namespace Star;
using V=StringView;
std::string hex(std::string_view s){static char const* d="0123456789abcdef";std::string out;for(unsigned char c:s){out+=d[c>>4];out+=d[c&15];}return out;}
struct Marker:std::runtime_error{using std::runtime_error::runtime_error;};
int main(){
 for(bool any:{false,true})for(unsigned scenario=0;scenario!=7;++scenario){
  std::string backing=scenario==0?"a":"a,b,c",replacement="u,v,w";
  auto receiver=std::make_unique<V>(backing);V separator(",");
  std::vector<std::string> values;unsigned calls=0;std::exception_ptr original;
  auto token=[&](V s,size_t offset,size_t length){values.push_back(hex(s.utf8()));values.push_back(std::to_string(offset));values.push_back(std::to_string(length));};
  auto throwOriginal=[&](){try{throw Marker("terminal-marker");}catch(...){original=std::current_exception();throw;}};
  auto callback=[&](V s,size_t offset,size_t length){
   token(s,offset,length);++calls;
   if(scenario==5 && calls==1)throwOriginal();
   if(scenario==6 && calls==1)separator=V(":"); // callee already owns its pattern copy
   if(scenario==4 && calls==1)*receiver=V(replacement);
   bool terminal=(scenario==0)||(calls==3);
   if(terminal && scenario<=4){
    if(scenario==3){
     V nested("q:r");
     auto nestedCallback=[&](V n,size_t o,size_t l){values.push_back("nested");token(n,o,l);};
     if(any)nested.forEachSplitAnyView(V(":"),nestedCallback);else nested.forEachSplitView(V(":"),nestedCallback);
    }
    receiver.reset();values.push_back("deleted");
    if(scenario==2)throwOriginal();
   }
  };
  try{
   // The object may die in the terminal callback. Neither this driver nor the
   // original method may inspect its receiver after that callback returns.
   V* address=receiver.get();
   if(any)address->forEachSplitAnyView(separator,callback);else address->forEachSplitView(separator,callback);
  }catch(Marker const& e){values.push_back(e.what());values.push_back(original==std::current_exception()?"same-exception":"wrong-exception");}
  values.push_back("calls="+std::to_string(calls));values.push_back(receiver?"alive":"dead");
  std::cout<<"{\"id\":\""<<(any?"any":"pattern")<<'-'<<scenario<<"\",\"value\":[";
  for(size_t i=0;i<values.size();++i){if(i)std::cout<<',';std::cout<<'\"'<<values[i]<<'\"';}std::cout<<"]}\n";
 }
}
