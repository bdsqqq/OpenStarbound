#include "abi.h"
#include <iostream>
#define main original_main
#include "../lab.cpp"
#undef main
int main(int argc,char** argv){int rc=original_main(argc,argv);for(unsigned m=0;m<34;++m)std::cerr<<m<<'\t'<<file_host_count(m,0)<<'\t'<<file_host_count(m,1)<<'\t'<<file_host_count(m,2)<<'\n';return rc;}
