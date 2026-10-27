#define main lifecycle_main
#define need lifecycle_need
#include "lifecycle.cpp"
#undef need
#undef main
#define main scalar_main
#define need scalar_need
#include "scalar.cpp"
#undef need
#undef main
#define main probe_main
#define need probe_need
#include "probe.cpp"
#undef need
#undef main
int main(int argc,char**){if(argc>1){try{size_t n;while(std::cin>>n){ProxyBoundaryWeightedPool<int> p;for(size_t i=0;i<n;++i){double w;std::cin>>w;p.add(w,int(i));}double target;std::cin>>target;ProxyRandomSource r;r.value=target;auto result=p.selectIndex(r);if(result==NPos)std::cout<<-1;else std::cout<<result;std::cout<<'\n';}return 0;}catch(std::exception const&e){std::cerr<<e.what()<<'\n';return 1;}}WpBoundary::Frame absent;auto fabricated=WpBoundary::reply(SB_WP_BORROW);if(absent.hasBorrowCapability(fabricated))return 11;absent.borrowReturned=true;if(!absent.hasBorrowCapability(fabricated))return 12;char name[]="combined",current[]="current",reference[]="reference";char* a[]{name,current};char* b[]{name,reference};if(lifecycle_main(2,a)||lifecycle_main(2,b)||scalar_main()||probe_main(1,a))return 13;std::cout<<"PASS\tmissing-borrow-capability-rejected\n";return 0;}
