// Included inside TtlNativeR1. These are native observations, not Rust proof.
inline std::vector<std::string> life;
inline int live=0, copies=0, moves=0,copyFault=0,producerCopies=0,producerCalls=0;
inline bool assignFault=false;
inline std::function<void(int)> destructorHook;
struct Value {
 int n;
 explicit Value(int n=0):n(n){++live;life.push_back("new:"+std::to_string(n));}
 Value(Value const& x):n(x.n){life.push_back("copy:"+std::to_string(n));if(++copies==copyFault)throw Fault("value-copy\x05");++live;}
 Value(Value&& x):n(x.n){++live;++moves;life.push_back("move:"+std::to_string(n));}
 Value& operator=(Value const& x){life.push_back("copy-assign:"+std::to_string(x.n));n=x.n;return *this;}
 Value& operator=(Value&& x){life.push_back("move-assign:"+std::to_string(x.n));n=x.n;if(assignFault){n=-999;throw Fault("value-assign\x06");}return *this;}
 ~Value(){life.push_back("destroy:"+std::to_string(n));--live;if(destructorHook)destructorHook(n);}
};
struct Producer {
 int n;std::exception_ptr error;
 Producer(int n,std::exception_ptr error={}):n(n),error(error){}
 Producer(Producer const& x):n(x.n),error(x.error){++producerCopies;life.push_back("producer-copy");}
 Value operator()(Key const&) const{++producerCalls;life.push_back("producer-call");if(error)std::rethrow_exception(error);return Value(n);}
};
template<class C> std::string vstate(C const& c){auto keys=c.keys();auto vals=c.values();std::vector<std::string> p;for(size_t i=0;i<keys.size();++i)p.push_back(std::to_string(keys[i].n)+":"+std::to_string(vals[i].n));return join(p);}
void property(std::string const& name,bool ok){std::cout<<"property\t"<<name<<"\t"<<ok<<"\n";if(!ok)throw Fault("property "+name);}
template<class C> void lifecycle(std::string const& alias){
 const int initial=live;std::vector<std::string> properties;
 life.clear();copies=moves=producerCopies=producerCalls=0;copyFault=0;assignFault=false;
 {
  C c(10000,0,8,false);c.set(Key(1),Value(10));c.set(Key(2),Value(20));
  auto p=c.ptr(Key(1));c.ptr(Key(2));property(alias+"-pointer-identity",c.ptr(Key(1))==p&&p->n==10);
  {auto snapshot=c.values();property(alias+"-values-independent",snapshot.size()==2);snapshot[0].n=999;}
  property(alias+"-values-not-moved-from-cache",c.ptr(Key(1))->n==10&&c.ptr(Key(2))->n==20);
  C copied(c);copied.set(Key(1),Value(99));property(alias+"-copy-independent",c.ptr(Key(1))->n==10&&copied.ptr(Key(1))->n==99);
  C moved(std::move(c));property(alias+"-implicit-move-copies-map",c.currentSize()==moved.currentSize()&&c.ptr(Key(1))!=moved.ptr(Key(1)));
  C assigned;assigned=std::move(c);property(alias+"-move-assignment-copies-map",c.currentSize()==assigned.currentSize()&&c.ptr(Key(1))!=assigned.ptr(Key(1))&&assigned.maxSize()==8);
  Producer producer(30);int before=producerCopies;auto& r=c.get(Key(3),producer);
  property(alias+"-producer-const-byvalue",producerCopies>before&&producerCalls==1&&r.n==30);
  before=producerCopies;c.get(Key(3),producer);property(alias+"-hit-still-copies-producer",producerCopies>before&&producerCalls==1);
  std::exception_ptr saved;try{throw Fault("saved-producer\x07");}catch(...){saved=std::current_exception();}
  bool same=false;try{c.get(Key(4),Producer(40,saved));}catch(...){same=std::current_exception()==saved;}
  property(alias+"-exception-ptr-identity",same&&c.ptr(Key(4))==nullptr);
  auto beforeState=vstate(c);Value argument(50);copies=0;copyFault=1;timeCalls=randomCalls=0;bool caught=false;
  try{c.set(Key(5),argument);}catch(Fault const& x){caught=std::string(x.what())=="value-copy\x05";}copyFault=0;
  property(alias+"-set-argument-copy-before-clock",caught&&vstate(c)==beforeState&&timeCalls==0&&randomCalls==0);
  // Negative smear throws from real Random too. The by-value argument must unwind.
  c.setTimeSmear(-1);int at=live;caught=false;
  try{c.set(Key(5),Value(50));}catch(Star::StarException const& x){caught=std::string(x.what())=="(StarException) Maximum bound in randInt must be >= minimum bound!";}
  property(alias+"-random-error-no-insert-balanced",caught&&live==at&&c.ptr(Key(5))==nullptr);c.setTimeSmear(0);
  c.set(Key(6),Value(60));assignFault=true;caught=false;
  try{c.set(Key(6),Value(66));}catch(Fault const& x){caught=std::string(x.what())=="value-assign\x06";}assignFault=false;
  property(alias+"-native-pair-assignment-partial-value",caught&&c.ptr(Key(6))->n==-999);
  c.set(Key(9),Value(90));int reentries=0;
  destructorHook=[&](int n){if(n==777&&reentries==0){++reentries;life.push_back("destructor-reentry");c.remove(Key(9));}};
  auto& produced=c.get(Key(7),[](Key const&){return Value(777);});destructorHook={};
  property(alias+"-prvalue-destructor-reentry",produced.n==777&&reentries==1&&c.ptr(Key(9))==nullptr);
  c.set(Key(9),Value(90));reentries=0;copies=0;copyFault=1;caught=false;
  destructorHook=[&](int n){if(n==888&&std::uncaught_exceptions()>0&&reentries==0){++reentries;life.push_back("unwind-destructor-reentry");c.remove(Key(9));}};
  try{c.get(Key(10),[](Key const&){return Value(888);});}catch(Fault const& x){caught=std::string(x.what())=="value-copy\x05";}
  destructorHook={};copyFault=0;
  property(alias+"-insertion-unwind-destructor-reentry",caught&&reentries==1&&c.ptr(Key(9))==nullptr&&c.ptr(Key(10))==nullptr);
  // Filter policy is native and copyable; thrown filter preserves its exception object.
  c.set(Key(8),Value(80));same=false;
  try{c.removeWhere([&](Key const&,Value& v){++v.n;std::rethrow_exception(saved);return false;});}catch(...){same=std::current_exception()==saved;}
  property(alias+"-filter-exception-identity",same);
  // A copy failure in the range temporary must destroy its already-copied prefix.
  at=live;copies=0;copyFault=2;caught=false;
  try{auto values=c.values();(void)values;}catch(Fault const& x){caught=std::string(x.what())=="value-copy\x05";}copyFault=0;
  property(alias+"-values-prefix-unwind",caught&&live==at);
 }
 property(alias+"-balanced-native-lifetimes",live==initial);
 std::cout<<"trace\t"<<alias<<"\t"<<join(life)<<"\n";
}
void lifecycles(){
 using Actual=Star::TtlCache<Key,Value>;using Scripted=Star::ScriptTtlCache<Key,Value>;
 using AH=Star::HashTtlCache<Key,Value,Hash>;using SH=Star::ScriptHashTtlCache<Key,Value,Hash>;
 lifecycle<Actual>("actual-ordered");lifecycle<Scripted>("scripted-ordered");lifecycle<AH>("actual-hash");lifecycle<SH>("scripted-hash");
}
