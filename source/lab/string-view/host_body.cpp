#include "host_header.hpp"
#include <functional>
#include <stdexcept>
namespace Star::StringViewHost {
namespace {
struct Invalid {};
void require(bool ok){if(!ok)throw Invalid{};}
std::string_view const& view(Ctx& c,uint64_t role){
 require(role<=1);if(role)return c.pattern;require(c.view);return *c.view;
}
bool overlaps(void const* output,void const* base,size_t n){
 if(!base||!n)return false;
 auto o=reinterpret_cast<uintptr_t>(output),b=reinterpret_cast<uintptr_t>(base);
 // Reject representational overflow without arithmetic on an untrusted pointer.
 if(o>UINTPTR_MAX-sizeof(uint64_t)||b>UINTPTR_MAX-n)return true;
 return o<b+n&&b<o+sizeof(uint64_t);
}
void simple(Ctx& c,uint64_t mode){
 require(mode==c.mode);
 switch(mode+1){
  case 1:case 2:case 3:case 4:case 5:case 6:case 7:case 8:case 9:case 10:case 11:case 12:case 13:case 14:case 15:break;
  case 16:require(c.view);break;
  case 17:require(c.mutableView);c.viewResult=take(*c.mutableView);break;
  case 18:require(c.view);break; // allocation remains in the original wrapper return expression
  case 19:c.pointerResult=view(c,0).data();break;
  case 21:case 22:{auto& v=view(c,0);c.iteratorResult.emplace(mode==20?v.begin():v.end(),v.begin(),v.end());break;}
  case 50:require(c.mutableView);*c.mutableView=c.pattern;break;
  case 51:require(c.cstring);c.result=view(c,0).compare(c.cstring)==0;break;
  case 52:require(c.string);c.result=view(c,0).compare(*c.string)==0;break;
  case 53:require(c.starString);c.result=view(c,0).compare(c.starString->utf8())==0;break;
  case 54:c.result=view(c,0)==c.pattern;break;
  case 55:c.result=view(c,0)!=c.pattern;break;
  case 56:c.result=view(c,0)<c.pattern;break;
  case 57:require(c.stream);*c.stream<<view(c,0);break;
  case 58:require(c.formatter&&c.formatContext);c.appender.emplace(c.formatter->format(view(c,0),*c.formatContext));break;
  default:throw Invalid{};
 }
}
}
uint32_t host(void* opaque,uint32_t op,uint64_t a,uint64_t b,uint64_t d,uint64_t* out) noexcept {
 if(!opaque||!out||reinterpret_cast<uintptr_t>(opaque)%alignof(Ctx))return 2;
 auto& c=*static_cast<Ctx*>(opaque);
 // Only known object spans are checked. This is not arbitrary pointer proof.
 auto address=reinterpret_cast<uintptr_t>(out);
 if(address%alignof(uint64_t)||address>UINTPTR_MAX-sizeof(uint64_t)||overlaps(out,&c,sizeof(c)))return 2;
 if(c.mode>=58)return 2;
 // FINISH must not inspect a possibly deleted receiver or its view.
 if(op!=SV_FINISH){
  if(overlaps(out,c.view,sizeof(std::string_view))||overlaps(out,c.mutableView,sizeof(std::string_view)))return 2;
  if(c.view&&overlaps(out,c.view->data(),c.view->size()))return 2;
  if(c.mutableView&&overlaps(out,c.mutableView->data(),c.mutableView->size()))return 2;
  if(overlaps(out,c.callback,sizeof(StringView::SplitCallback))||overlaps(out,c.stream,sizeof(std::ostream))||
     overlaps(out,c.formatter,sizeof(fmt::formatter<std::string_view>))||overlaps(out,c.formatContext,sizeof(fmt::format_context))||
     overlaps(out,c.string,sizeof(std::string))||overlaps(out,c.starString,sizeof(String)))return 2;
  if(c.string&&overlaps(out,c.string->data(),c.string->size()))return 2;
  if(overlaps(out,c.pattern.data(),c.pattern.size()))return 2;
 }
 *out=0;if(c.pending)return 1;
 try {
  switch(op){
   case SV_ARG:require(a<6&&!b&&!d);*out=c.args[a];break;
   case SV_BYTES:require(!b&&!d);*out=view(c,a).size();break;
   case SV_LENGTH:{require(!b&&!d);auto& v=view(c,a);*out=utf8Length(v.data(),v.size());break;}
   case SV_VALID:{require(!a&&!b&&!d);auto& v=view(c,0);*out=isValidUtf8(v.data(),v.size());break;}
   case SV_INIT:{require(a<4&&b<2&&d==0);auto& v=view(c,b);c.iter[a].emplace(v.begin(),v.begin(),v.end());c.roles[a]=b;break;}
   case SV_ADVANCE:require(a<4&&c.iter[a]&&!b&&!d);++*c.iter[a];break;
   case SV_END:{require(a<4&&b<2&&c.iter[a]&&c.roles[a]==b&&!d);auto& v=view(c,b);*out=*c.iter[a]==StringView::const_iterator(v.end(),v.begin(),v.end());break;}
   case SV_READ:require(a<4&&c.iter[a]&&!b&&!d);*out=**c.iter[a];break;
   case SV_COPY:require(a<4&&b<4&&c.iter[b]&&!d);c.iter[a]=c.iter[b];c.roles[a]=c.roles[b];break;
   case SV_EQUAL:require(a<=UINT32_MAX&&b<=UINT32_MAX&&d<=1);*out=String::charEqual(a,b,d?String::CaseInsensitive:String::CaseSensitive);break;
   case SV_SPACE:require(a<=UINT32_MAX&&!b&&!d);*out=String::isSpace(a);break;
   case SV_LOWER:require(a<=UINT32_MAX&&!b&&!d);*out=String::toLower(a);break;
   case SV_FIND_BYTES:require(b<=1&&!d);*out=b?view(c,0).find_first_of(c.pattern,a):view(c,0).find(c.pattern,a);break;
   case SV_CALLBACK:{require(c.callback&&d<=1);auto& v=view(c,0);require(a<=v.size()&&b<=v.size()-a);
    // Form every argument before invocation; no receiver read after callback.
    if(d)(*c.callback)(v.substr(a),a,b);else (*c.callback)(v.substr(a,b),a,b);break;}
   case SV_THROW_AT:require(!b&&!d);throw OutOfRangeException(strf("Out of range in StringView::at({})",a));
   case SV_THROW_SUBSTR:require(!d);throw OutOfRangeException(strf("out of range in StringView::substr({}, {})",a,b));
   case SV_SUBSTR:require(a<4&&b<4&&c.iter[a]&&c.iter[b]&&c.roles[a]==0&&c.roles[b]==0&&!d);c.viewResult=std::string_view(&*c.iter[a]->base(),c.iter[b]->base()-c.iter[a]->base());break;
   case SV_NATIVE_COMPARE:require(!a&&!b&&!d);c.comparison=view(c,0).compare(c.pattern);*out=static_cast<uint64_t>(static_cast<int64_t>(c.comparison));break;
   case SV_SIMPLE:require(!b&&!d);simple(c,a);break;
   case SV_RETURN:require(!b&&!d);c.result=a;break;
   case SV_FINISH:require(!a&&!b&&!d);break;
   case SV_ASSERT_BOUNDARY:require(!d);starAssert(a<=b);break;
   default:throw Invalid{};
  }
  return 0;
 }catch(Invalid const&){return 2;}catch(...){c.pending=std::current_exception();return 1;}
}
void execute(uint32_t mode,Ctx& c){
 c.mode=mode;auto status=sb_string_view_run(mode,&c,host);
 if(status==1&&c.pending)std::rethrow_exception(c.pending);
 if(status)throw std::runtime_error("StringView host protocol rejected");
}
}
