namespace TtlControls {
using namespace Star;
inline int defect=0;
uint32_t fake(void*,SbTtlRequest const*,SbTtlReply* r){
 *r={24,1,SB_TTL_I64,0,42};
 switch(defect){case 1:r->size=23;break;case 2:r->version=2;break;case 3:r->tag=SB_TTL_U64;break;case 4:r->reserved=1;break;case 5:return SB_TTL_EXCEPTION;case 6:return SB_TTL_INVALID;case 7:return SB_TTL_PANIC;case 8:return 99;case 9:r->tag=SB_TTL_BOOL;r->value=2;break;case 10:r->tag=SB_TTL_VOID;r->value=1;break;}
 return 0;
}
struct Clock {static int64_t now(){return 1;}static int random(int,int){return 0;}};
inline std::vector<std::string> events;
inline int live=0,moves=0,failMove=0,reentries=0;
inline std::exception_ptr savedMove;
inline std::function<void()> unwindHook;
struct ThrowingValue {
 int n;
 explicit ThrowingValue(int n=0):n(n){++live;}
 ThrowingValue(ThrowingValue const& x):n(x.n){++live;events.push_back("copy:"+std::to_string(n));}
 ThrowingValue(ThrowingValue&& x):n(x.n){events.push_back("move:"+std::to_string(n));if(++moves==failMove)std::rethrow_exception(savedMove);++live;}
 ThrowingValue& operator=(ThrowingValue const& x){n=x.n;return *this;}
 ThrowingValue& operator=(ThrowingValue&& x){n=x.n;return *this;}
 ~ThrowingValue(){--live;events.push_back("destroy:"+std::to_string(n)+":"+std::to_string(std::uncaught_exceptions()));if(std::uncaught_exceptions() && unwindHook && !reentries){++reentries;unwindHook();}}
};
template<class C> std::vector<std::string> valuesUnwind(){
 int initial=live;std::vector<std::string> trace;
 {
  C c(10000,0,8,false);for(int k: {1,2,3,99})c.set(k,ThrowingValue(k));
  events.clear();moves=0;failMove=7;reentries=0;
  try{throw std::runtime_error("saved-values-move");}catch(...){savedMove=std::current_exception();}
  unwindHook=[&]{events.push_back("values-range-unwind-reentry");c.remove(99);};
  bool same=false;try{auto result=c.values();(void)result;}catch(...){same=std::current_exception()==savedMove;}
  unwindHook={};failMove=0;
  if(!same || reentries!=1 || live!=initial+3 || c.ptr(99)!=nullptr)throw std::runtime_error("values nested unwind contract");
  // One range copy and one successfully appended result prefix both unwind.
  int prefix=0;for(auto const& e:events)if(e=="destroy:1:1")++prefix;
  if(prefix!=2)throw std::runtime_error("values named-result prefix did not unwind");
  trace=events;
 }
 if(live!=initial)throw std::runtime_error("values lifetimes unbalanced");
 return trace;
}
void check(char const* name,bool pass){std::cout<<"control\t"<<name<<"\t"<<pass<<"\n";if(!pass)throw std::runtime_error(name);}
void run(){
 int opaque=0;SbTtlReply sentinel{24,1,789,0,654},out;
 defect=0;out=sentinel;check("valid-controller",sb_ttl_run(SB_TTL_TTL,0,&opaque,fake,&out)==0 && out.value==42 && out.tag==SB_TTL_I64);
 for(int i=0;i<3;++i){out=sentinel;if(i==0)out.size=23;else if(i==1)out.version=2;else out.reserved=1;auto original=out;check(i==0?"root-result-bad-size":i==1?"root-result-bad-version":"root-result-bad-reserved",sb_ttl_run(SB_TTL_TTL,0,&opaque,fake,&out)==SB_TTL_INVALID && !std::memcmp(&out,&original,24));}
 for(int i=1;i<=8;++i){defect=i;out=sentinel;auto s=sb_ttl_run(SB_TTL_TTL,0,&opaque,fake,&out);check(("controller-reply-"+std::to_string(i)).c_str(),s==(i==5?1:i==7?3:2) && !std::memcmp(&out,&sentinel,24));}
 defect=9;out=sentinel;check("noncanonical-bool-output",sb_ttl_run(SB_TTL_UPDATE,0,&opaque,fake,&out)==2 && !std::memcmp(&out,&sentinel,24));
 defect=10;out=sentinel;check("nonzero-void-output",sb_ttl_run(SB_TTL_CLEAR,0,&opaque,fake,&out)==2 && !std::memcmp(&out,&sentinel,24));
 defect=0;
 for(uint32_t m=0;m<19;++m)for(uint32_t s=1;s<4;++s)if(!((m==9&&s==1)||(m==15&&s==2)||(m==18&&s==3))){out=sentinel;check("invalid-mode-stage",sb_ttl_run(m,s,&opaque,fake,&out)==2 && !std::memcmp(&out,&sentinel,24));}
 out=sentinel;check("invalid-mode",sb_ttl_run(19,0,&opaque,fake,&out)==2 && !std::memcmp(&out,&sentinel,24));
 check("invalid-stage",sb_ttl_run(0,4,&opaque,fake,&out)==2);
 check("null-context",sb_ttl_run(0,0,nullptr,fake,&out)==2);check("null-host",sb_ttl_run(0,0,&opaque,nullptr,&out)==2);check("null-result",sb_ttl_run(0,0,&opaque,fake,nullptr)==2);
 using L=LruCache<int,pair<int64_t,int>>;L l;int64_t ttl=10;int smear=0;bool update=false;
 using C=TtlBoundaryHost::Context<L,SB_TTL_TTL,Clock>;C c(l,ttl,smear,update);
 SbTtlRequest valid{24,1,SB_TTL_READ_TTL,0,0};
 out=TtlBoundaryHost::reply();check("native-positive",C::host(&c,&valid,&out)==0 && out.value==10);
 for(int i=0;i<7;++i){auto q=valid;switch(i){case 0:q.size=0;break;case 1:q.version=2;break;case 2:q.op=0;break;case 3:q.op=32;break;case 4:q.reserved=1;break;case 5:q.arg=1;break;case 6:q.op=SB_TTL_ARG;break;}out=sentinel;check("native-malformed-request",C::host(&c,&q,&out)==2 && !std::memcmp(&out,&sentinel,24));}
 check("native-null-context",C::host(nullptr,&valid,&out)==2);check("native-null-request",C::host(&c,nullptr,&out)==2);check("native-null-output",C::host(&c,&valid,nullptr)==2);
 using W=TtlBoundaryHost::Context<L,SB_TTL_SET_TTL,Clock>;W w(l,ttl,smear,update);SbTtlRequest writeTtl{24,1,SB_TTL_WRITE_TTL,0,1000};
 for(int i=0;i<3;++i){out=sentinel;if(i==0)out.size=23;else if(i==1)out.version=2;else out.reserved=1;auto original=out;auto before=ttl;check(i==0?"native-reply-bad-size-before-mutation":i==1?"native-reply-bad-version-before-mutation":"native-reply-bad-reserved-before-mutation",W::host(&w,&writeTtl,&out)==SB_TTL_INVALID && ttl==before && !std::memcmp(&out,&original,24));}
 using V=TtlBoundaryHost::Context<L,SB_TTL_VALUES,Clock>;V v(l,ttl,smear,update);auto q=valid;q.op=SB_TTL_VALUES_END;out=sentinel;
 check("native-outside-continuation",V::host(&v,&q,&out)==2 && !std::memcmp(&out,&sentinel,24));
 using P=TtlBoundaryHost::Context<L,SB_TTL_PTR,Clock>;P p(l,ttl,smear,update);q.op=SB_TTL_PAIR_STAMP_NATIVE;out=sentinel;
 check("native-missing-borrower",P::host(&p,&q,&out)==2 && !std::memcmp(&out,&sentinel,24));
 l.set(1,make_pair(int64_t(1),2));int nativeKey=1;p.key=&nativeKey;q.op=SB_TTL_LRU_PTR;out=sentinel;check("native-ptr-bind",P::host(&p,&q,&out)==0 && p.pair);
 q.op=SB_TTL_PAIR_VALUE_BORROW;out=sentinel;check("native-leaf15-void-root-ref-distinction",P::host(&p,&q,&out)==0 && out.tag==SB_TTL_VOID && out.value==0 && p.value==&p.pair->second);
 std::exception_ptr saved;try{throw std::runtime_error("original");}catch(...){saved=std::current_exception();}c.pending=saved;out=sentinel;
 check("native-pending-output-preserved",C::host(&c,&valid,&out)==1 && !std::memcmp(&out,&sentinel,24));
 bool same=false;try{c.execute();}catch(...){same=std::current_exception()==saved;}check("saved-exception-ptr",same);
 BoundaryTtlCache<int,int> actual;actual.set(1,2);
 // Mock-only omission hooks are not linked or represented as actual-Rust tests.
 check("actual-rust-native-borrow-positive",actual.ptr(1) && *actual.ptr(1)==2 && actual.get(1,[](int){return 3;})==2);
 actual.clear();check("clear-selected",actual.currentSize()==0 && sb_ttl_count(SB_TTL_CLEAR,0)>0);
 auto ordered=valuesUnwind<TtlCache<int,ThrowingValue>>();
 auto orderedBoundary=valuesUnwind<BoundaryTtlCache<int,ThrowingValue>>();
 check("nested-values-ordered-exact-unwind-trace",ordered==orderedBoundary);
 auto hash=valuesUnwind<HashTtlCache<int,ThrowingValue>>();
 auto hashBoundary=valuesUnwind<BoundaryHashTtlCache<int,ThrowingValue>>();
 check("nested-values-hash-exact-unwind-trace",hash==hashBoundary);
 for(auto const& event:ordered)std::cout<<"values-unwind\tordered\t"<<event<<"\n";
 for(auto const& event:hash)std::cout<<"values-unwind\thash\t"<<event<<"\n";
 std::exception_ptr refreshSaved;try{throw std::runtime_error("saved-refresh");}catch(...){refreshSaved=std::current_exception();}
 actual.set(1,2);bool refreshSame=false;try{actual.cleanup([&](int,int){std::rethrow_exception(refreshSaved);return false;});}catch(...){refreshSame=std::current_exception()==refreshSaved;}
 check("nested-cleanup-saved-exception-ptr",refreshSame && actual.currentSize()==1);
}
}
