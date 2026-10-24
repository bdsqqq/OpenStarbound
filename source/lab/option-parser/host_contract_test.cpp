#include "host_contract.hpp"
#include "StarOptionParser.hpp"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <functional>
#include <vector>
#include <cstdlib>
#undef assert
#define assert(condition) do { if (!(condition)) { std::cerr << "FAIL line " << __LINE__ << ": " << #condition << '\n'; std::exit(1); } } while (false)
using namespace Star;
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
extern void (*star_option_parser_lab_before_run)(uint32_t,void*,StarOptionParserLabHost);
extern void (*star_option_parser_lab_after_op)(uint32_t,uint64_t,uint32_t);
#endif
namespace {
bool operations[34]={},templates[24]={};
void* liveHelpContext=nullptr;StarOptionParserLabHost liveHelpHost=nullptr;
void* latestContext=nullptr;StarOptionParserLabHost latestHost=nullptr;bool checkingPending=false;unsigned checkedPending=0;
void observed(uint32_t op,uint64_t a,uint32_t status){if(status==0||status==1){operations[op]=true;if(op==5||op==29||op==30||op==31)templates[a]=true;}
 if(status==1&&!checkingPending){checkingPending=true;uint64_t out=91;assert(latestHost(latestContext,33,0,0,0,&out)==1&&out==91);++checkedPending;checkingPending=false;}
}
void preflight(uint32_t mode,void* ctx,StarOptionParserLabHost host){
 latestContext=ctx;latestHost=host;
 if(mode==7){liveHelpContext=ctx;liveHelpHost=host;}
 uint64_t output=0x12345678;
 assert(host(ctx,0,0,0,0,&output)==2&&output==0x12345678);
 assert(host(ctx,33,1,0,0,&output)==2&&output==0x12345678);
 assert(host(ctx,33,0,0,0,&output)==2&&output==0x12345678);
 assert(host(ctx,1,0,1,0,&output)==2&&output==0x12345678);
 assert(host(ctx,1,0,0,0,nullptr)==2);
 assert(host(ctx,1,0,0,0,reinterpret_cast<uint64_t*>(UINTPTR_MAX-7))==2);
 assert(host(nullptr,1,0,0,0,&output)==2);
 assert(host(static_cast<char*>(ctx)+1,1,0,0,0,&output)==2&&output==0x12345678);
 assert(host(ctx,1,0,0,0,reinterpret_cast<uint64_t*>(ctx))==2);
 alignas(8) char unaligned[16]={};assert(host(ctx,1,0,0,0,reinterpret_cast<uint64_t*>(unaligned+1))==2);
 assert(host(ctx,20,0,0,0,&output)==2&&output==0x12345678);
 if(mode==7)assert(host(ctx,27,6,0,0,&output)==2&&output==0x12345678);
}

struct Buffer:std::stringbuf {
 std::vector<std::string> chunks; std::function<void()> once;std::exception_ptr fault;bool partial=false;
 std::streamsize xsputn(char const* p,std::streamsize n)override {
  chunks.emplace_back(p,n);auto f=std::move(once);once={};if(f)f();if(partial){auto k=n/2;std::stringbuf::xsputn(p,k);if(fault)std::rethrow_exception(fault);return k;}if(fault)std::rethrow_exception(fault);return std::stringbuf::xsputn(p,n);
 }
};
std::vector<unsigned> opaqueOps;
uint32_t opaqueHelp(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out){assert(p==nullptr);assert(!b&&!c);opaqueOps.push_back(op);if(op==27)*out=1;else if(op==24)*out=0;else {assert(op==28||op==23||op==26||op==33||(op==31&&a==10));*out=0;}return 0;}
struct ParseStep {uint32_t op;uint64_t a=0,b=0,c=0,out=0;};
struct ParseScript {std::vector<ParseStep> steps;size_t next=0;};
uint32_t opaqueParse(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out){auto& s=*static_cast<ParseScript*>(p);assert(s.next<s.steps.size());auto e=s.steps[s.next++];assert(op==e.op&&a==e.a&&b==e.b&&c==e.c);*out=e.out;return 0;}
struct Script {unsigned calls=0;uint32_t status=0;std::vector<unsigned> ops;};
uint32_t scripted(void* p,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out){auto& s=*static_cast<Script*>(p);++s.calls;s.ops.push_back(op);assert(!b&&!c);if(s.status)return s.status;if(op==1){assert(a==0);*out=0;}else {assert(op==33);*out=0;}return 0;}
}
int main() try {
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
 star_option_parser_lab_before_run=preflight;star_option_parser_lab_after_op=observed;
#endif
 assert(star_option_parser_lab_controller(7,nullptr,opaqueHelp)==0);assert(opaqueOps.back()==33);
 // Counterfactual scalar host, NOT native parser state: parameter consumption,
 // --, positional handling, required errors and sticky Multiple cardinality.
 ParseScript opaque{{{6},{7,0,0,0,1},{8},{9},{10,0,0,0,1},{11},{12},{13,0,0,0,1},{14},{7,0,0,0,1},{16},{15},{17},{19},{20},{22},
  {7,0,0,0,1},{8},{9,0,0,0,1},{22},{7,0,0,0,1},{8},{9},{21},{22},{7},
  {23},{24,0,0,0,1},{14,1,1,0,1},{15,1,0,0,1},{17,1},{30,19},{25},{24},{26},
  {23,1},{24,1,0,0,1},{15,2,0,0,2},{25,1},{24,1,0,0,1},{15,2,0,0,1},{25,1},{24,1},{26,1},{32,0,0,0,2},{33}}};
 assert(star_option_parser_lab_controller(6,&opaque,opaqueParse)==0&&opaque.next==opaque.steps.size());
 Script s;assert(star_option_parser_lab_controller(8,&s,scripted)==2&&s.calls==0);assert(star_option_parser_lab_controller(0,&s,nullptr)==2&&s.calls==0);
 assert(star_option_parser_lab_controller(0,&s,scripted)==0);assert((s.ops==std::vector<unsigned>{1,33}));s={};s.status=1;assert(star_option_parser_lab_controller(0,&s,scripted)==1&&s.calls==1);
 for(uint32_t status:{2u,3u,UINT32_MAX}){s={};s.status=status;assert(star_option_parser_lab_controller(0,&s,scripted)==2&&s.calls==1);}
 OptionParser p;p.setCommandName("cmd");p.setSummary("sum");p.addSwitch("verbose","v");p.addParameter("output","FILE",OptionParser::Required,"out");p.addArgument("target",OptionParser::Required,"tgt");p.setAdditionalHelp("extra");
 std::string expected="cmd: sum\n\nCommand Line Usage: cmd [-verbose] -output <FILE> <target>\n  -verbose\t- v\n  -output <FILE>\t- out\n  <target>\t- tgt\n\nextra\n";
 Buffer b;std::ostream os(&b);p.printHelp(os);assert(b.str()==expected);assert(b.chunks.size()==6);assert(b.chunks[0]=="cmd: sum\n\n");
 auto parsed=p.parseOptions({"-output","one","-output","two","tail"});assert(parsed.first.parameters.get("output")==StringList{"one"});assert(parsed.first.arguments==StringList{"tail"});assert(parsed.second==StringList{"Option with argument '-output' specified multiple times"});
 auto q=p.parseOptions({"--","--","-output"});assert((q.first.arguments==StringList{"-output"}));assert(q.second==StringList{"Missing required flag with argument '-output'"});
 auto v=p.parseOptions({"-output","--","-verbose","-verbose","tail"});assert(v.second.empty());assert(v.first.switches.size()==1);assert(v.first.parameters.get("output")==StringList{"--"});
 bool duplicate=false;try{p.addSwitch("verbose");}catch(OptionParserException const& e){duplicate=true;}assert(duplicate);
 OptionParser fresh;fresh.setCommandName("old");fresh.setSummary("sum");Buffer late;std::ostream los(&late);late.once=[&]{fresh.setCommandName("new");fresh.setAdditionalHelp("late");fresh.addSwitch("a","ad");fresh.addArgument("x",OptionParser::Optional,"xd");};fresh.printHelp(los);assert(late.str()=="old: sum\n\nCommand Line Usage: new [-a] [<x>]\n  -a\t- ad\n  <x>\t- xd\n\nlate\n");
 OptionParser active;active.addSwitch("a","ad");Buffer ins;std::ostream ios(&ins);int seen=0;std::function<void()> hook;hook=[&]{if(++seen==2)active.addSwitch("b","bd");else ins.once=hook;};ins.once=hook;active.printHelp(ios);assert(ins.str()=="Command Line Usage: [-a]\n  -a\t- ad\n  -b\t- bd\n");
 Buffer width;std::ostream wos(&width);wos<<std::setfill('.')<<std::setw(16);OptionParser small;small.setCommandName("x");small.printHelp(wos);assert(width.chunks.size()==3);assert(width.str()==std::string(12,'.')+"x:\n\nCommand Line Usage: x\n");
 Buffer bad;bad.partial=true;auto fault=std::make_exception_ptr(std::runtime_error("sentinel"));bad.fault=fault;std::ostream bos(&bad);bos.exceptions(std::ios::badbit);bool same=false;try{small.printHelp(bos);}catch(...){same=std::current_exception()==fault;}assert(same);assert(bad.str()=="x:");
 Buffer shortWrite;shortWrite.partial=true;std::ostream sos(&shortWrite);small.printHelp(sos);assert(sos.bad());assert(shortWrite.str()=="x:");assert(shortWrite.chunks.size()==1);
 Buffer reentry;std::ostream ros(&reentry);reentry.once=[&]{
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
 uint64_t out=99;assert(liveHelpHost(liveHelpContext,27,0,0,0,&out)==2&&out==99);
#endif
 std::ostringstream nested;small.printHelp(nested);assert(nested.str()=="x:\n\nCommand Line Usage: x\n");};small.printHelp(ros);assert(reentry.str()=="x:\n\nCommand Line Usage: x\n");
 OptionParser many;many.addParameter("m","M",OptionParser::Multiple);many.addArgument("rest",OptionParser::Multiple);many.addArgument("required",OptionParser::Required);auto m=many.parseOptions({"-m","a","-m","b"});assert(m.first.parameters.get("m").size()==2);assert(m.second==StringList{"Too few positional arguments given, expected at least 1 got 0"});
 auto unknown=small.parseOptions({"-wat"});assert(unknown.second==StringList{"No such option '-wat'"});
 auto missing=p.parseOptions({"-output"});assert(missing.second.size()==3);
 auto excess=small.parseOptions({"one"});assert(excess.second==StringList{"Too many positional arguments given, expected at most 0 got 1"});
 bool duplicateParameter=false;try{p.addParameter("output","x",OptionParser::Optional);}catch(OptionParserException const&){duplicateParameter=true;}assert(duplicateParameter);
 OptionParser layouts;layouts.setSummary("summary");layouts.addSwitch("empty");layouts.addParameter("optional","O",OptionParser::Optional);layouts.addParameter("multiple","M",OptionParser::Multiple);layouts.addArgument("optional",OptionParser::Optional);layouts.addArgument("required",OptionParser::Required);layouts.addArgument("multiple",OptionParser::Multiple);std::ostringstream layout;layouts.printHelp(layout);assert(layout.str()=="summary\n\nCommand Line Usage: [-empty] [-optional <O>] [-multiple <M>]... [<optional>] <required> [<multiple>...]\n");
 OptionParser enum3;enum3.addParameter("three","T",static_cast<OptionParser::RequirementMode>(3));enum3.addArgument("three",static_cast<OptionParser::RequirementMode>(3));std::ostringstream e3;enum3.printHelp(e3);assert(e3.str()=="Command Line Usage: [<three>...]\n");
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
 for(unsigned i=1;i<=33;++i)assert(operations[i]);for(unsigned i=0;i<24;++i)assert(templates[i]);assert(checkedPending>=3);
#endif
 std::cout<<"prototype public smoke + opaque controller + live stream tests pass\n";
} catch(std::exception const& e) {std::cerr<<"FAIL native exception: "<<e.what()<<'\n';return 1;} catch(...) {std::cerr<<"FAIL unexpected native exception\n";return 1;}
