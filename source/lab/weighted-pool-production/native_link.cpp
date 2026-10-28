#include "StarWeightedPool.hpp"
#include <iostream>
int main(){
 Star::WeightedPool<int> p;p.add(1,9);
 if(p.size()!=1||p.item(0)!=9||p.select(uint64_t(17))!=9)return 1;
 auto selected=p.selectUniques(1,uint64_t(17));
 if(selected!=Star::List<int>{9})return 2;
 p.clear();if(!p.empty())return 3;
 std::cout<<"PASS\tactual-production-default-off-without-rust-link\n";
 return 0;
}
