#include <iostream>
#include <string>
std::string events;
struct Value { Value(){events+='V';} Value(Value const&)=delete; Value(Value&&)=delete; ~Value(){events+='v';} };
struct Temp { Temp(){events+='T';} ~Temp(){events+='t';} };
Value encode(Temp const&) { events+='E'; return Value(); }
Value leaf() { return encode(Temp()); }
Value throwing() { Temp t; events+='X'; throw 7; }
using Leaf=Value(*)(); constexpr Leaf table[]={leaf,throwing};
unsigned select(unsigned method){events+='S'; return method;}
Value facade(unsigned method){auto action=select(method); events+='R'; return table[action]();}
int main(){
  {auto value=facade(0); events+='H';}
  events+='|';try{auto value=facade(1);}catch(int){events+='C';}
  std::cout<<events<<'\n';
}
