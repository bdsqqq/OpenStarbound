#include "abi.h"
static thread_local uint64_t counts[34][3]{};
extern "C" uint64_t file_host_count(uint32_t m,uint32_t e){return m<34&&e<3?counts[m][e]:0;}
extern "C" uint32_t file_host_run(uint32_t m,void* ctx,file_host_fn host){
 if(m>=34||!ctx||!host)return 2;
 ++counts[m][0];
 uint32_t status=0; uint64_t v=0;
 auto call=[&](uint32_t op,uint64_t a=0){if(status)return uint64_t(0);status=host(ctx,op,a,0,0,&v);if(status>3)status=2;return v;};
 try {
 switch(m){
 case 0: if(!call(0))call(1);if(!call(2))call(3);break;
 case 1:call(0);while(!status&&call(1)){call(2);if(call(3))call(4);else call(5);call(6);}call(7);call(8);break;
 case 2:call(0);while(!status&&!call(1)){call(2);call(3);}break;
 case 3:call(0);break;
 case 4:case 5:while(!status&&!call(0)){uint64_t n=call(1);if(m==4)call(2,n);else for(uint64_t i=0;!status&&i<n;++i)call(2,i);}break;
 case 7:call(0);break;
 case 12:{unsigned n=static_cast<unsigned>(call(0));for(unsigned i=n;!status&&i>0;--i){call(1,i);if(call(2))call(3);call(4);}break;}
 case 17:case 18:case 29:if(!call(0))call(1);call(2);break;
 case 20:if(!call(0))call(1);call(2);break;
 case 21:case 22:if(!call(0))call(1);if(!call(2))call(3);call(4);break;
 case 26:if(call(0))call(1);call(2);break;
 case 27:call(0);if(call(1))call(2);call(3);break;
 case 28:{bool temp=!call(0);if(temp)call(1);call(2);if(temp)call(3);break;}
 case 30:call(0);if(call(1))call(2);call(3);call(4);break;
 case 31:if(call(0))call(1);call(2);call(3);break;
 case 32:if(call(0))call(1);else call(2);break;
 case 33:if(call(0)){call(1);call(2);}break;
 default:call(0);break;
 }
 }catch(...){status=3;}
 ++counts[m][status?2:1];return status;
}
