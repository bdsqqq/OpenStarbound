#include "StarFile.hpp"
#include <iostream>
int main(){std::cout<<sizeof(Star::File)<<' '<<alignof(Star::File)<<' '<<sizeof(Star::IODevice)<<' '<<sizeof(Star::String)<<' '<<sizeof(Star::List<std::pair<Star::String,bool>>)<<' '<<sizeof(Star::ByteArray)<<'\n';}
