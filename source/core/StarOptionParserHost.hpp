#ifndef STAR_OPTION_PARSER_HOST_HPP
#define STAR_OPTION_PARSER_HOST_HPP
#include "StarRustOptionParser.h"
#include <optional>
#include <exception>
#include <type_traits>
#include <limits>

// Native leaves preserve full expressions and scratch lifetimes; Rust owns control flow.
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
using BeforeRun = void (*)(uint32_t,void*,StarOptionParserLabHost);
using AfterOp = void (*)(uint32_t,uint64_t,uint32_t);
BeforeRun star_option_parser_lab_before_run=nullptr;
AfterOp star_option_parser_lab_after_op=nullptr;
#endif
namespace Star { namespace {
template<class S,class P,class A,class Text,class Map,class Args> struct Context {
 using Opt=Variant<S,P>;
 // Private record names are supplied legally from member definitions below;
 // inference keeps parse/help borrows const without mirroring their layout.
 uint32_t mode; Text &name,&summary,&additional;Map& options;Args& arguments;
 OptionParser const* nativeOwner=nullptr;
 static_assert(sizeof(size_t)==sizeof(uint64_t),"lab scalar arithmetic requires 64-bit size_t");
 inline static thread_local Context* live=nullptr;Context* nextLive=nullptr;
 Context(OptionParser const* owner,uint32_t m,Text& n,Text& s,Text& h,Map& o,Args& a):mode(m),name(n),summary(s),additional(h),options(o),arguments(a),nativeOwner(owner){nextLive=live;live=this;}
 Context(Context const&)=delete;Context& operator=(Context const&)=delete;
 ~Context(){auto p=&live;while(*p&&*p!=this)p=&(*p)->nextLive;if(*p)*p=nextLive;}
 String* moved=nullptr;String const* payloadFlag=nullptr;String* payloadArgument=nullptr;String* description=nullptr;OptionParser::RequirementMode requirement=OptionParser::Optional;
 StringList const* input=nullptr;OptionParser::Options* result=nullptr;StringList* errors=nullptr;std::ostream* stream=nullptr;
 using Input=decltype(makeSIterator(std::declval<StringList const&>()));
 using OIter=decltype(std::declval<Map&>().begin());using AIter=decltype(std::declval<Args&>().begin());
 std::optional<String> command;
 std::optional<Input> in;std::optional<OIter> oi,oe;std::optional<AIter> ai,ae;
 unsigned completedOptions=0,completedArguments=0;bool applied=false,usageWritten=false,countRead=false;
 std::optional<String> flag;std::optional<Maybe<Opt>> lookup;std::optional<String> value;
 String const* token=nullptr;StringList* list=nullptr;
 std::exception_ptr pending;bool busy=false,finished=false;
 bool currentOption()const{return oi && oe && *oi!=*oe;}
 bool currentArgument()const{return ai && ae && *ai!=*ae;}
 Opt const& option(uint64_t source)const {return source==0?**lookup:(*oi)->second;}
 P const& parameter(uint64_t source)const{return option(source).template get<P>();}
 bool validOption(uint64_t source) const {return source==0?(lookup && bool(*lookup)):source==1&&currentOption();}
 uint32_t invoke(uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out) {
  if(!out || reinterpret_cast<uintptr_t>(out)%alignof(uint64_t) || reinterpret_cast<uintptr_t>(out)>UINTPTR_MAX-sizeof(uint64_t))return 2;
  auto p=reinterpret_cast<uintptr_t>(out), start=reinterpret_cast<uintptr_t>(this);if(p<start+sizeof(*this)&&p+8>start)return 2;
  auto overlaps=[&](auto const* object){if(!object)return false;auto begin=reinterpret_cast<uintptr_t>(object);return p<begin+sizeof(*object)&&p+8>begin;};
  if(overlaps(nativeOwner)||overlaps(&name)||overlaps(&summary)||overlaps(&additional)||overlaps(&options)||overlaps(&arguments)||overlaps(moved)||overlaps(payloadFlag)||overlaps(payloadArgument)||overlaps(description)||overlaps(input)||overlaps(result)||overlaps(errors)||overlaps(stream))return 2;
  if(pending)return 1;if(busy||finished||op==0||op>33)return 2;
  if((op!=14 && op!=30) && (b||c))return 2;if(op==14 && (b>1||c))return 2;if(op==30 && a<20 && (b||c))return 2;
  if(op!=1&&op!=5&&op!=14&&op!=15&&op!=17&&!(op>=23&&op<=27)&&op!=29&&op!=30&&op!=31&&a)return 2;
  if(op>=1&&op<=4&&applied)return 2;
  if(((op>=6&&op<=13)||(op>=16&&op<=22)||op==30||op==32)&&mode!=6)return 2;
  if(((op>=27&&op<=29)||op==31)&&mode!=7)return 2;
  if((op==14||op==15)&&mode<6)return 2;
  uint64_t v=0; busy=true;
  struct Guard{bool& b;~Guard(){b=false;}} guard{busy};
  try {
   switch(op) {
   case 1: if(mode>2||a!=mode||!moved)return 2;
    if constexpr(!std::is_const_v<Text>){if(a==0)name=std::move(*moved);if(a==1)summary=std::move(*moved);if(a==2)additional=std::move(*moved);}else return 2;break;
   case 2: if(mode!=3)return 2;if constexpr(!std::is_const_v<Map>)v=options.insert(*payloadFlag,S{*payloadFlag,std::move(*description)}).second;else return 2;break;
   case 3: if(mode!=4)return 2;if constexpr(!std::is_const_v<Map>)v=options.insert(*payloadFlag,P{*payloadFlag,std::move(*payloadArgument),requirement,std::move(*description)}).second;else return 2;break;
   case 4: if(mode!=5)return 2;if constexpr(!std::is_const_v<Args>)arguments.append(A{std::move(*payloadArgument),requirement,std::move(*description)});else return 2;break;
   case 5:if(mode==3&&a==22)throw OptionParserException::format("Duplicate switch '-{}' added",*payloadFlag);if(mode==4&&a==23)throw OptionParserException::format("Duplicate flag '-{}' added",*payloadFlag);return 2;
   case 6:if(mode!=6||in)return 2;in.emplace(makeSIterator(*input));break;
   case 7:if(mode!=6||!in)return 2;v=in->hasNext();break;
   case 8:if(mode!=6||!in||token||!in->hasNext())return 2;token=&in->next();break;
   case 9:if(!token)return 2;v=*token=="--";break;
   case 10:if(!token)return 2;v=token->beginsWith("-");break;
   case 11:if(!token||flag)return 2;flag.emplace(token->substr(1));break;
   case 12:if(!flag||lookup)return 2;lookup.emplace(options.maybe(*flag));break;
   case 13:if(!lookup)return 2;v=bool(*lookup);break;
   case 14:if(!validOption(a))return 2;v=b==0?option(a).template is<S>():option(a).template is<P>();break;
   case 15:if(a==2){if(!currentArgument())return 2;v=(*ai)->requirementMode;}else {if(!validOption(a)||!option(a).template is<P>())return 2;v=parameter(a).requirementMode;}break;
   case 16:if(mode!=6||!in||!in->hasNext()||value)return 2;value.emplace(in->next());break;
   case 17:if(mode!=6||a>1||(a==0?!flag:!currentOption()))return 2;v=result->parameters.contains(a==0?*flag:(*oi)->first);break;
   case 18:if(mode!=6||!flag)return 2;result->switches.add(std::move(*flag));break;
   case 19:if(mode!=6||!flag||list)return 2;list=&result->parameters[std::move(*flag)];break;
   case 20:if(!list||!value)return 2;list->append(std::move(*value));break;
   case 21:if(mode!=6||!token)return 2;result->arguments.append(*token);break;
   case 22:if(mode!=6||!token)return 2;value.reset();lookup.reset();flag.reset();token=nullptr;list=nullptr;break;
   case 23:if(mode<6||a>1||oi||ai)return 2;
    if(mode==6){if(!in||in->hasNext()||token)return 2;if(a==0&&(completedOptions||completedArguments))return 2;if(a==1&&(completedOptions!=1||completedArguments))return 2;}
    if(mode==7){if(!command)return 2;if(a==0&&(completedOptions!=completedArguments||completedOptions>1||(completedOptions==1&&!usageWritten)))return 2;if(a==1&&completedOptions!=completedArguments+1)return 2;}
    if(a==0){if(oi)return 2;oi.emplace(options.begin());oe.emplace(options.end());}else{if(ai)return 2;ai.emplace(arguments.begin());ae.emplace(arguments.end());}break;
   case 24:if(a==0&&oi&&oe)v=*oi!=*oe;else if(a==1&&ai&&ae)v=*ai!=*ae;else return 2;break;
   case 25:if(a==0&&currentOption())++*oi;else if(a==1&&currentArgument())++*ai;else return 2;break;
   case 26:if(a==0&&oi&&oe&&*oi==*oe){oe.reset();oi.reset();++completedOptions;}else if(a==1&&ai&&ae&&*ai==*ae){ae.reset();ai.reset();++completedArguments;}else return 2;break;
   case 27:if(mode!=7)return 2;switch(a){case 0:v=name.empty();break;case 1:v=summary.empty();break;case 2:v=additional.empty();break;case 3:if(!currentOption()||!option(1).template is<S>())return 2;v=option(1).template get<S>().description.empty();break;case 4:if(!currentOption()||!option(1).template is<P>())return 2;v=parameter(1).description.empty();break;case 5:if(!currentArgument())return 2;v=(*ai)->description.empty();break;default:return 2;}break;
   case 28:if(mode!=7||command)return 2;command.emplace();break;
   case 29:if(mode!=7||!command||a<3||a>9)return 2;
    if(a==3){if(!currentOption()||!option(1).template is<S>())return 2;*command+=strf(" [-{}]",(*oi)->first);}
    else if(a<=6){if(!currentOption()||!option(1).template is<P>())return 2;auto const& p=parameter(1);if(a==4)*command+=strf(" [-{} <{}>]",p.flag,p.argument);if(a==5)*command+=strf(" -{} <{}>",p.flag,p.argument);if(a==6)*command+=strf(" [-{} <{}>]...",p.flag,p.argument);}
    else {if(!currentArgument())return 2;auto const& p=**ai;if(a==7)*command+=strf(" [<{}>]",p.argumentName);if(a==8)*command+=strf(" <{}>",p.argumentName);if(a==9)*command+=strf(" [<{}>...]",p.argumentName);}break;
   case 30:if(mode!=6||a<16||a>21)return 2;
    if(a<=18){if(!flag)return 2;if(a==16)errors->append(strf("No such option '-{}'",*flag));if(a==17)errors->append(strf("Option '-{}' must be followed by an argument",*flag));if(a==18)errors->append(strf("Option with argument '-{}' specified multiple times",*flag));}
    if(a==19){if(!currentOption())return 2;errors->append(strf("Missing required flag with argument '-{}'",(*oi)->first));}
    if(a==20)errors->append(strf("Too few positional arguments given, expected at least {} got {}",b,c));
    if(a==21)errors->append(strf("Too many positional arguments given, expected at most {} got {}",b,c));break;
   case 31:if(mode!=7||!stream)return 2;
    if(a<=2&&command)return 2;
    if((a==10||a==11)&&(usageWritten||oi||ai||completedOptions!=1||completedArguments!=1))return 2;
    if(a>=12&&a<=14&&!usageWritten)return 2;
    if(a==15&&(oi||ai||completedOptions!=2||completedArguments!=2))return 2;
    switch(a){
    case 0:format(*stream,"{}: {}\n\n",name,summary);break;case 1:format(*stream,"{}:\n\n",name);break;case 2:format(*stream,"{}\n\n",summary);break;
    case 10:if(!command)return 2;format(*stream,"Command Line Usage:{}\n",*command);break;
    case 11:if(!command)return 2;format(*stream,"Command Line Usage: {}{}\n",name,*command);break;
    case 12:{if(!currentOption()||!option(1).template is<S>())return 2;auto const& p=option(1).template get<S>();format(*stream,"  -{}\t- {}\n",p.flag,p.description);break;}
    case 13:{if(!currentOption()||!option(1).template is<P>())return 2;auto const& p=parameter(1);format(*stream,"  -{} <{}>\t- {}\n",p.flag,p.argument,p.description);break;}
    case 14:{if(!currentArgument())return 2;auto const& p=**ai;format(*stream,"  <{}>\t- {}\n",p.argumentName,p.description);break;}
    case 15:format(*stream,"\n{}\n",additional);break;default:return 2;}break;
   case 32:if(mode!=6||completedOptions!=1||completedArguments!=1||oi||ai)return 2;v=result->arguments.size();countRead=true;break;
   case 33:if(token||flag||lookup||value||list||oi||ai)return 2;
    if(mode<6&&!applied)return 2;
    if(mode==6&&(!in||in->hasNext()||completedOptions!=1||completedArguments!=1||!countRead))return 2;
    if(mode==7&&(!command||completedOptions!=2||completedArguments!=2||!usageWritten))return 2;
    finished=true;break;
   }
   if(op>=1&&op<=4)applied=true;
   if(op==31&&(a==10||a==11))usageWritten=true;
   *out=v;return 0;
  }catch(...){pending=std::current_exception();return 1;}
 }
 static uint32_t host(void* ptr,uint32_t op,uint64_t a,uint64_t b,uint64_t c,uint64_t* out){auto known=live;while(known&&known!=ptr)known=known->nextLive;if(!known)return 2;auto s=known->invoke(op,a,b,c,out);
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
  if(star_option_parser_lab_after_op)star_option_parser_lab_after_op(op,a,s);
#endif
  return s;}
 void run(){
#ifdef STAR_OPTION_PARSER_LAB_TEST_HOOKS
  if(star_option_parser_lab_before_run)star_option_parser_lab_before_run(mode,this,host);
#endif
  auto s=star_option_parser_run(mode,this,host);if(pending)std::rethrow_exception(pending);if(s)throw std::runtime_error("Rust option parser host contract rejected controller");}
};
template<class S,class P,class A,class T,class M,class L> auto makeContext(OptionParser const* owner,uint32_t mode,T& n,T& s,T& h,M& m,L& l){return Context<S,P,A,T,M,L>{owner,mode,n,s,h,m,l};}
}}

#endif
