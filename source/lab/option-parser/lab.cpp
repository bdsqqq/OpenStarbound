#ifdef LAB_REFERENCE
#include "StarOptionParser.reference.hpp"
using Parser = OptionReference::OptionParser;
using ParseException = OptionReference::OptionParserException;
#else
#include "StarOptionParser.original.hpp"
using Parser = Star::OptionParser;
using ParseException = Star::OptionParserException;
#endif
#include <sstream>
#include <iomanip>
#include <functional>
#include <stdexcept>
using namespace Star;
std::string id;
std::string hex(std::string const& s) { static char const* h="0123456789abcdef"; std::string r; for(unsigned char c:s){r+=h[c>>4];r+=h[c&15];}return r; }
void emit(std::string k,std::string v){std::cout<<id<<'\t'<<k<<'\t'<<hex(v)<<'\n';}
void parse(Parser const& p,StringList const& a){try {auto r=p.parseOptions(a); for(auto const& s:r.first.switches)emit("switch",s.utf8());for(auto const& kv:r.first.parameters){emit("parameter",kv.first.utf8());for(auto const& v:kv.second)emit("value",v.utf8());}for(auto const& v:r.first.arguments)emit("argument",v.utf8());for(auto const& e:r.second)emit("error",e.utf8());emit("done","");}catch(std::exception const& e){emit("exception",e.what());}}
void help(Parser const& p){std::ostringstream o;p.printHelp(o);emit("help",o.str());}
Parser basic(){Parser p;p.setCommandName("cmd");p.setSummary("sum");p.addSwitch("verbose","v");p.addParameter("output","FILE",Parser::Required,"out");p.addArgument("target",Parser::Required,"tgt");p.setAdditionalHelp("extra");return p;}
// Every native stream call is observable, including prefix-only writes and callbacks.
struct Buffer:std::streambuf {
 std::string bytes; std::vector<std::string> events;std::function<void(size_t)> callback;size_t calls=0,fail=0;bool throwing=false;std::exception_ptr sentinel=std::make_exception_ptr(std::runtime_error("stream sentinel"));
 std::streamsize xsputn(char const* s,std::streamsize n) override {events.push_back("xsputn:"+std::to_string(n)+":"+hex(std::string(s,n)));size_t k=++calls;if(callback)callback(k);if(k==fail){if(throwing)std::rethrow_exception(sentinel);auto count=n? n-1:0;bytes.append(s,count);return count;}bytes.append(s,n);return n;}
 int_type overflow(int_type c) override {events.push_back("overflow:"+std::to_string(c));if(!traits_type::eq_int_type(c,traits_type::eof()))bytes+=traits_type::to_char_type(c);return c;}
 int sync() override {events.push_back("sync");return 0;}
};
void streamCase(int mode){auto p=basic();Buffer b,t;std::ostream os(&b),tie(&t);os.tie(&tie);os.fill('.');os.width((mode==1||mode==12||mode==13)?18:0);if(mode==1)os.setf(std::ios::left,std::ios::adjustfield);if(mode==12)os.setf(std::ios::right,std::ios::adjustfield);if(mode==13)os.setf(std::ios::internal,std::ios::adjustfield);if(mode==2||mode==3){b.fail=mode==2?1:3;}if(mode==4||mode==5){b.fail=mode==4?1:3;b.throwing=true;os.exceptions(std::ios::badbit);}if(mode==6)b.callback=[&](size_t n){if(n==1){p.setCommandName("NEW");p.setSummary("fresh");p.setAdditionalHelp("late");p.addSwitch("early","early-desc");p.addArgument("more",Parser::Optional,"more-desc");}};if(mode==7)b.callback=[&](size_t n){if(n==2){p.addSwitch("late","late-desc");p.addArgument("latearg",Parser::Optional,"latearg-desc");p.setAdditionalHelp("late-extra");}};if(mode==8)b.callback=[&](size_t n){if(n==1){std::ostringstream nested;p.printHelp(nested);emit("nested",nested.str());p.setCommandName("AFTER");}};if(mode==9)os.setstate(std::ios::failbit);if(mode==10||mode==11){b.fail=mode==10?1:3;b.throwing=true;}if(mode==14)b.callback=[&](size_t n){if(n==3)p.addSwitch("during","during-desc");};
 try{p.printHelp(os);emit("escaped","none");}catch(...){emit("escaped",std::current_exception()==b.sentinel?"sentinel":"other");}emit("bytes",b.bytes);for(auto const& e:b.events)emit("trace",e);for(auto const& e:t.events)emit("tie",e);emit("state",std::to_string(os.rdstate()));emit("width",std::to_string(os.width()));emit("fill",std::to_string(os.fill()));emit("flags",std::to_string(os.flags()));emit("exceptions",std::to_string(os.exceptions()));help(p);
}
int main(){
 {Parser p;id="unknown";parse(p,{"-wat"});}
 {Parser p;p.addParameter("p","V",Parser::Optional);id="missing";parse(p,{"-p"});id="duplicate";parse(p,{"-p","one","-p","two","tail"});id="param-end";parse(p,{"-p","--","-wat"});}
 {Parser p;p.addSwitch("s");id="switch";parse(p,{"-s","-s"});id="ends";parse(p,{"--","--","-s","--"});p.addSwitch("-help");p.addSwitch("");id="dash";parse(p,{"--help","-"});}
 {Parser p;p.addParameter("z","Z",Parser::Required);p.addParameter("a","A",Parser::Required);p.addArgument("x",Parser::Required);id="required";parse(p,{"-wat"});}
 {Parser p;p.addArgument("all",Parser::Multiple);p.addArgument("last",Parser::Required);id="multiple-empty";parse(p,{});id="multiple-many";parse(p,{"x","y","z"});}
 {auto p=basic();id="help";help(p);id="basic-parse";parse(p,{"-verbose","-output","file","dest"});Parser copy=p;Parser moved=std::move(copy);id="copy-move";help(moved);parse(moved,{"-output","copy","target"});}
 {Parser p;String alias="alias";p.setCommandName(alias);alias="changed";p.setSummary("summary");p.setAdditionalHelp("help");p.addSwitch("x","first");id="duplicate-switch";try{p.addSwitch("x","second");}catch(ParseException const& e){emit("registration-error",e.what());}help(p);id="collision";try{p.addParameter("x","Y",Parser::Required,"replacement");}catch(ParseException const& e){emit("registration-error",e.what());}help(p);parse(p,{"-x"});}
 {Parser p;p.addParameter("p","V",Parser::Multiple,"many");p.addParameter("q","Q",Parser::Optional,"one");p.addArgument("x",Parser::Optional);id="registration-order";help(p);parse(p,{"-p","1","-q","2","-p","3"});}
 {Parser p;p.addArgument("binary",Parser::Multiple);p.addSwitch(String("nul\0flag",8),String("d\0esc",5));p.addSwitch("雪","説明");id="binary";parse(p,{String("a\0b",3),String("-nul\0flag",9),"-雪"});help(p);id="invalid-utf8";parse(p,{String("-\xff",2)});}
 {Parser p;p.addArgument("third",static_cast<Parser::RequirementMode>(3));p.addParameter("third","V",static_cast<Parser::RequirementMode>(3),"nonenumerator");id="enum3";help(p);parse(p,{"-third","1","-third","2","pos"});}
 for(int m=0;m<15;++m){id="stream"+std::to_string(m);streamCase(m);}
 {Parser p;String flag="p";p.addParameter(flag,"VALUE",Parser::Optional,"original");flag="changed";id="parameter-collisions";try{p.addSwitch("p","replacement");}catch(ParseException const& e){emit("registration-error",e.what());}try{p.addParameter("p","REPLACE",Parser::Required,"new");}catch(ParseException const& e){emit("registration-error",e.what());}help(p);parse(p,{"-p","kept"});}
 // Bounded deterministic combinations exercise persistent definitions and output order.
 for(unsigned seed=0;seed<256;++seed){Parser p;p.addSwitch("z");p.addSwitch("a");p.addParameter("p","P",static_cast<Parser::RequirementMode>(seed%4));p.addParameter("q","Q",static_cast<Parser::RequirementMode>((seed/4)%4));p.addArgument("x",static_cast<Parser::RequirementMode>((seed/16)%4));if(seed&128)p.addArgument("y",Parser::Required);StringList args;char const* words[]={"-z","-a","-p","-q","--","-wat","pos",""};unsigned state=seed+17;for(unsigned n=0;n<seed%13;++n){state=state*1664525+1013904223;args.append(words[(state>>24)%8]);}id="combination"+std::to_string(seed);parse(p,args);help(p);}
 for(int m=0;m<4;++m){Parser p;if(m&1)p.setCommandName("n");if(m&2)p.setSummary("s");id="metadata"+std::to_string(m);help(p);}
}
