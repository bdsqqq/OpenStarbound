#include "host_header.hpp"
namespace Star {
using namespace StringViewHost;
String::String(StringView s) : m_string(bridge(0,s.utf8())) {}
String::String(std::string_view s) : m_string(bridge(1,s)) {}
String& String::operator+=(StringView s){m_string+=bridge(2,s.utf8());return *this;}
String& String::operator+=(std::string_view s){m_string+=bridge(3,s);return *this;}
StringView::StringView(){Ctx c;execute(4,c);}
StringView::StringView(StringView const& s):m_view(s.m_view){Ctx c;execute(5,c);}
StringView::StringView(StringView&& s) noexcept:m_view(std::move(s.m_view)){Ctx c;execute(6,c);}
StringView::StringView(String const& s):m_view(s.utf8()){Ctx c;execute(7,c);}
StringView::StringView(char const* s):m_view(s){Ctx c;execute(8,c);}
StringView::StringView(char const* s,size_t n):m_view(s,n){Ctx c;execute(9,c);}
StringView::StringView(std::string_view const& s):m_view(s){Ctx c;execute(10,c);}
StringView::StringView(std::string_view&& s) noexcept:m_view(std::move(s)){Ctx c;execute(11,c);}
StringView::StringView(std::string const& s):m_view(s){Ctx c;execute(12,c);}
StringView::StringView(Char const* s):m_view((char const*)s,sizeof(*s)){Ctx c;execute(13,c);}
StringView::StringView(Char const* s,size_t n):m_view((char const*)s,n*sizeof(*s)){Ctx c;execute(14,c);}
std::string_view const& StringView::utf8() const{Ctx c;c.view=&m_view;execute(15,c);return m_view;}
std::string_view StringView::takeUtf8(){Ctx c;c.mutableView=&m_view;execute(16,c);return c.viewResult;}
ByteArray StringView::utf8Bytes() const{Ctx c;c.view=&m_view;execute(17,c);return ByteArray(m_view.data(),m_view.size());}
char const* StringView::utf8Ptr() const{Ctx c;c.view=&m_view;execute(18,c);return c.pointerResult;}
size_t StringView::utf8Size() const{Ctx c;c.view=&m_view;execute(19,c);return c.result;}
StringView::const_iterator StringView::begin() const{Ctx c;c.view=&m_view;execute(20,c);return *c.iteratorResult;}
StringView::const_iterator StringView::end() const{Ctx c;c.view=&m_view;execute(21,c);return *c.iteratorResult;}
size_t StringView::size() const{Ctx c;c.view=&m_view;execute(22,c);return c.result;}
size_t StringView::length() const{Ctx c;c.view=&m_view;execute(23,c);return c.result;}
bool StringView::isValid() const{Ctx c;c.view=&m_view;execute(24,c);return c.result;}
bool StringView::empty() const{Ctx c;c.view=&m_view;execute(25,c);return c.result;}
StringView::Char StringView::operator[](size_t index) const{Ctx c;c.view=&m_view;c.args[0]=index;execute(26,c);return c.result;}
StringView::Char StringView::at(size_t index) const{Ctx c;c.view=&m_view;c.args[0]=index;execute(27,c);return c.result;}
bool StringView::endsWith(StringView end,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=end.m_view;c.args[2]=cs;execute(28,c);return c.result;}
bool StringView::endsWith(Char end,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.args[0]=end;c.args[2]=cs;execute(29,c);return c.result;}
bool StringView::beginsWith(StringView beg,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=beg.m_view;c.args[2]=cs;execute(30,c);return c.result;}
bool StringView::beginsWith(Char beg,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.args[0]=beg;c.args[2]=cs;execute(31,c);return c.result;}
void StringView::forEachSplitAnyView(StringView chars,SplitCallback callback) const{Ctx c;c.view=&m_view;c.pattern=chars.m_view;c.callback=&callback;execute(32,c);}
void StringView::forEachSplitView(StringView pattern,SplitCallback callback) const{Ctx c;c.view=&m_view;c.pattern=pattern.m_view;c.callback=&callback;execute(33,c);}
bool StringView::hasChar(Char ch) const{Ctx c;c.view=&m_view;c.args[0]=ch;execute(34,c);return c.result;}
bool StringView::hasCharOrWhitespace(Char ch) const{Ctx c;c.view=&m_view;c.args[0]=ch;execute(35,c);return c.result;}
size_t StringView::find(Char ch,size_t pos,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.args[0]=ch;c.args[1]=pos;c.args[2]=cs;execute(36,c);return c.result;}
size_t StringView::find(StringView str,size_t pos,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=str.m_view;c.args[1]=pos;c.args[2]=cs;execute(37,c);return c.result;}
size_t StringView::findLast(Char ch,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.args[0]=ch;c.args[2]=cs;execute(38,c);return c.result;}
size_t StringView::findLast(StringView str,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=str.m_view;c.args[2]=cs;execute(39,c);return c.result;}
size_t StringView::findFirstOf(StringView pattern,size_t beg) const{Ctx c;c.view=&m_view;c.pattern=pattern.m_view;c.args[1]=beg;execute(40,c);return c.result;}
size_t StringView::findFirstNotOf(StringView pattern,size_t beg) const{Ctx c;c.view=&m_view;c.pattern=pattern.m_view;c.args[1]=beg;execute(41,c);return c.result;}
size_t StringView::findNextBoundary(size_t index,bool backwards) const{Ctx c;c.view=&m_view;c.args[0]=index;c.args[1]=backwards;execute(42,c);return c.result;}
bool StringView::contains(StringView s,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=s.m_view;c.args[2]=cs;execute(43,c);return c.result;}
int StringView::compare(StringView s,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=s.m_view;c.args[2]=cs;execute(44,c);return static_cast<int>(static_cast<int64_t>(c.result));}
bool StringView::equals(StringView s,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=s.m_view;c.args[2]=cs;execute(45,c);return c.result;}
bool StringView::equalsIgnoreCase(StringView s) const{Ctx c;c.view=&m_view;c.pattern=s.m_view;execute(46,c);return c.result;}
StringView StringView::substr(size_t pos,size_t n) const{Ctx c;c.view=&m_view;c.args[0]=pos;c.args[1]=n;execute(47,c);return StringView(c.viewResult.data(),c.viewResult.size());}
int StringView::compare(size_t so,size_t sl,StringView other,size_t oo,size_t ol,CaseSensitivity cs) const{Ctx c;c.view=&m_view;c.pattern=other.m_view;c.args[0]=so;c.args[1]=sl;c.args[2]=cs;c.args[3]=oo;c.args[4]=ol;execute(48,c);return static_cast<int>(static_cast<int64_t>(c.result));}
StringView& StringView::operator=(StringView s){Ctx c;c.mutableView=&m_view;c.pattern=s.m_view;execute(49,c);return *this;}
bool operator==(StringView s1,const char* s2){Ctx c;c.view=&s1.m_view;c.cstring=s2;execute(50,c);return c.result;}
bool operator==(StringView s1,std::string const& s2){Ctx c;c.view=&s1.m_view;c.string=&s2;execute(51,c);return c.result;}
bool operator==(StringView s1,String const& s2){Ctx c;c.view=&s1.m_view;c.starString=&s2;execute(52,c);return c.result;}
bool operator==(StringView s1,StringView s2){Ctx c;c.view=&s1.m_view;c.pattern=s2.m_view;execute(53,c);return c.result;}
bool operator!=(StringView s1,StringView s2){Ctx c;c.view=&s1.m_view;c.pattern=s2.m_view;execute(54,c);return c.result;}
bool operator<(StringView s1,StringView s2){Ctx c;c.view=&s1.m_view;c.pattern=s2.m_view;execute(55,c);return c.result;}
std::ostream& operator<<(std::ostream& os,StringView const& s){Ctx c;c.view=&s.utf8();c.stream=&os;execute(56,c);return os;}
}
fmt::appender fmt::formatter<Star::StringView>::format(Star::StringView const& s,format_context& ctx) const{
 Star::StringViewHost::Ctx c;c.view=&s.utf8();c.formatter=this;c.formatContext=&ctx;Star::StringViewHost::execute(57,c);return *c.appender;
}
