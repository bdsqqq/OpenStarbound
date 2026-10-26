#ifdef STAR_USE_RUST_STRING_VIEW
#include "StarStringViewHost.hpp"
namespace Star {
using namespace StringViewRust;
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
 Star::StringViewRust::Ctx c;c.view=&s.utf8();c.formatter=this;c.formatContext=&ctx;Star::StringViewRust::execute(57,c);return *c.appender;
}

#else
#include "StarStringView.hpp"

namespace Star {
// To string
String::String(StringView s) : m_string(s.utf8()) {}
String::String(std::string_view s) : m_string(s) {}

String& String::operator+=(StringView s) {
  m_string += s.utf8();
  return *this;
}

String& String::operator+=(std::string_view s) {
  m_string += s;
  return *this;
}

StringView::StringView() {}
StringView::StringView(StringView const& s) : m_view(s.m_view) {}
StringView::StringView(StringView&& s) noexcept : m_view(std::move(s.m_view)) {};
StringView::StringView(String const& s) : m_view(s.utf8()) {};
StringView::StringView(char const* s) : m_view(s) {};
StringView::StringView(char const* s, size_t n) : m_view(s, n) {};

StringView::StringView(std::string_view const& s) : m_view(s) {};
StringView::StringView(std::string_view&& s) noexcept : m_view(std::move(s)) {};
StringView::StringView(std::string const& s) : m_view(s) {}

StringView::StringView(Char const* s) : m_view((char const*)s, sizeof(*s)) {}
StringView::StringView(Char const* s, size_t n) : m_view((char const*)s, n * sizeof(*s)) {};

std::string_view const& StringView::utf8() const {
  return m_view;
}

std::string_view StringView::takeUtf8() {
  return take(m_view);
}

ByteArray StringView::utf8Bytes() const {
  return ByteArray(m_view.data(), m_view.size());
}

char const* StringView::utf8Ptr() const {
  return m_view.data();
}

size_t StringView::utf8Size() const {
  return m_view.size();
}

StringView::const_iterator StringView::begin() const {
  return const_iterator(m_view.begin(), m_view.begin(), m_view.end());
}

StringView::const_iterator StringView::end() const {
  return const_iterator(m_view.end(), m_view.begin(), m_view.end());
}

size_t StringView::size() const {
  return utf8Length(m_view.data(), m_view.size());
}

size_t StringView::length() const {
  return size();
}

bool StringView::isValid() const {
  return isValidUtf8(m_view.data(), m_view.size());
}

bool StringView::empty() const {
  return m_view.empty();
}

StringView::Char StringView::operator[](size_t index) const {
  auto it = begin();
  for (size_t i = 0; i < index; ++i)
    ++it;
  return *it;
}

StringView::Char StringView::at(size_t index) const {
  auto it = begin();
  auto itEnd = end();
  for (size_t i = 0; i < index; ++i) {
    ++it;
    if (it == itEnd)
      throw OutOfRangeException(strf("Out of range in StringView::at({})", i));
  }
  return *it;
}

bool StringView::endsWith(StringView end, CaseSensitivity cs) const {
  auto endsize = end.size();
  if (endsize == 0)
    return true;

  auto mysize = size();
  if (endsize > mysize)
    return false;

  return compare(mysize - endsize, NPos, end, 0, NPos, cs) == 0;
}
bool StringView::endsWith(Char end, CaseSensitivity cs) const {
  if (m_view.empty())
    return false;

  return String::charEqual(end, operator[](size() - 1), cs);
}

bool StringView::beginsWith(StringView beg, CaseSensitivity cs) const {
  if (beg.m_view.empty())
    return true;

  size_t begSize = beg.size();
  auto it = begin();
  auto itEnd = end();
  for (size_t i = 0; i != begSize; ++i)
  {
    if (it == itEnd)
      return false;
    it++;
  }

  return compare(0, begSize, beg, 0, NPos, cs) == 0;
}

bool StringView::beginsWith(Char beg, CaseSensitivity cs) const {
  if (m_view.empty())
    return false;

  return String::charEqual(beg, operator[](0), cs);
}

void StringView::forEachSplitAnyView(StringView chars, SplitCallback callback) const {
  if (chars.empty())
    return;

  size_t beg = 0;
  while (true) {
    size_t end = m_view.find_first_of(chars.m_view, beg);
    if (end == NPos) {
      callback(m_view.substr(beg), beg, m_view.size() - beg);
      break;
    }
    callback(m_view.substr(beg, end - beg), beg, end - beg);
    beg = end + 1;
  }
}

void StringView::forEachSplitView(StringView pattern, SplitCallback callback) const {
  if (pattern.empty())
    return;

  size_t beg = 0;
  while (true) {
    size_t end = m_view.find(pattern.m_view, beg);
    if (end == NPos) {
      callback(m_view.substr(beg), beg, m_view.size() - beg);
      break;
    }
    callback(m_view.substr(beg, end - beg), beg, end - beg);
    beg = end + pattern.m_view.size();
  }
}

bool StringView::hasChar(Char c) const {
  for (Char ch : *this)
    if (ch == c)
      return true;
  return false;
}

bool StringView::hasCharOrWhitespace(Char c) const {
  return empty() ? String::isSpace(c) : hasChar(c);
}

size_t StringView::find(Char c, size_t pos, CaseSensitivity cs) const {
  auto it = begin();
  for (size_t i = 0; i < pos; ++i) {
    if (it == end())
      break;
    ++it;
  }

  while (it != end()) {
    if (String::charEqual(c, *it, cs))
      return pos;
    ++pos;
    ++it;
  }

  return NPos;
}

size_t StringView::find(StringView str, size_t pos, CaseSensitivity cs) const {
  if (str.empty())
    return 0;

  auto it = begin();
  for (size_t i = 0; i < pos; ++i) {
    if (it == end())
      break;
    ++it;
  }

  const_iterator sit = str.begin();
  const_iterator mit = it;
  while (it != end()) {
    if (String::charEqual(*sit, *mit, cs)) {
      do {
        ++mit;
        ++sit;
        if (sit == str.end())
          return pos;
        else if (mit == end())
          break;
      } while (String::charEqual(*sit, *mit, cs));
      sit = str.begin();
    }
    ++pos;
    mit = ++it;
  }

  return NPos;
}

size_t StringView::findLast(Char c, CaseSensitivity cs) const {
  auto it = begin();

  size_t found = NPos;
  size_t pos = 0;
  while (it != end()) {
    if (String::charEqual(c, *it, cs))
      found = pos;
    ++pos;
    ++it;
  }

  return found;
}

size_t StringView::findLast(StringView str, CaseSensitivity cs) const {
  if (str.empty())
    return 0;

  size_t pos = 0;
  auto it = begin();
  size_t result = NPos;
  const_iterator sit = str.begin();
  const_iterator mit = it;
  while (it != end()) {
    if (String::charEqual(*sit, *mit, cs)) {
      do {
        ++mit;
        ++sit;
        if (sit == str.end()) {
          result = pos;
          break;
        }
        if (mit == end())
          break;
      } while (String::charEqual(*sit, *mit, cs));
      sit = str.begin();
    }
    ++pos;
    mit = ++it;
  }

  return result;
}

size_t StringView::findFirstOf(StringView pattern, size_t beg) const {
  auto it = begin();
  size_t i;
  for (i = 0; i < beg; ++i)
    ++it;

  while (it != end()) {
    if (pattern.hasCharOrWhitespace(*it))
      return i;
    ++it;
    ++i;
  }
  return NPos;
}

size_t StringView::findFirstNotOf(StringView pattern, size_t beg) const {
  auto it = begin();
  size_t i;
  for (i = 0; i < beg; ++i)
    ++it;

  while (it != end()) {
    if (!pattern.hasCharOrWhitespace(*it))
      return i;
    ++it;
    ++i;
  }
  return NPos;
}

size_t StringView::findNextBoundary(size_t index, bool backwards) const {
  //TODO: Make this faster.
  size_t mySize = size();
  starAssert(index <= mySize);
  if (!backwards && (index == mySize))
    return index;
  if (backwards) {
    if (index == 0)
      return 0;
    index--;
  }
  Char c = this->at(index);
  while (!String::isSpace(c)) {
    if (backwards && (index == 0))
      return 0;
    index += backwards ? -1 : 1;
    if (index == mySize)
      return mySize;
    c = this->at(index);
  }
  while (String::isSpace(c)) {
    if (backwards && (index == 0))
      return 0;
    index += backwards ? -1 : 1;
    if (index == mySize)
      return mySize;
    c = this->at(index);
  }
  if (backwards && !(index == mySize))
    return index + 1;
  return index;
}

bool StringView::contains(StringView s, CaseSensitivity cs) const {
  return find(s, 0, cs) != NPos;
}

int StringView::compare(StringView s, CaseSensitivity cs) const {
  if (cs == CaseSensitivity::CaseSensitive)
    return m_view.compare(s.m_view);
  else
    return compare(0, NPos, s, 0, NPos, cs);
}

bool StringView::equals(StringView s, CaseSensitivity cs) const {
  return compare(s, cs) == 0;
}

bool StringView::equalsIgnoreCase(StringView s) const {
  return compare(s, CaseSensitivity::CaseInsensitive) == 0;
}

StringView StringView::substr(size_t position, size_t n) const {
  StringView ret;
  auto itEnd = end();
  auto it = begin();

  for (size_t i = 0; i != position; ++i) {
    if (it == itEnd)
      throw OutOfRangeException(strf("out of range in StringView::substr({}, {})", position, n));
    it++;
  }

  const auto itStart = it;

  for (size_t i = 0; i != n; ++i) {
    if (it == itEnd)
      break;
    ++it;
  }

  return StringView(&*itStart.base(), it.base() - itStart.base());
}

int StringView::compare(size_t selfOffset, size_t selfLen, StringView other,
    size_t otherOffset, size_t otherLen, CaseSensitivity cs) const {
  auto selfIt = begin();
  auto otherIt = other.begin();

  while (selfOffset > 0 && selfIt != end()) {
    ++selfIt;
    --selfOffset;
  }

  while (otherOffset > 0 && otherIt != other.end()) {
    ++otherIt;
    --otherLen;
  }

  while (true) {
    if ((selfIt == end() || selfLen == 0) && (otherIt == other.end() || otherLen == 0))
      return 0;
    else if (selfIt == end() || selfLen == 0)
      return -1;
    else if (otherIt == other.end() || otherLen == 0)
      return 1;

    auto c1 = *selfIt;
    auto c2 = *otherIt;

    if (cs == CaseSensitivity::CaseInsensitive) {
      c1 = String::toLower(c1);
      c2 = String::toLower(c2);
    }

    if (c1 < c2)
      return -1;
    else if (c2 < c1)
      return 1;

    ++selfIt;
    ++otherIt;
    --selfLen;
    --otherLen;
  }
}

StringView& StringView::operator=(StringView s) {
  m_view = s.m_view;
  return *this;
}

bool operator==(StringView s1, const char* s2) {
  return s1.m_view.compare(s2) == 0;
}

bool operator==(StringView s1, std::string const& s2) {
  return s1.m_view.compare(s2) == 0;
}

bool operator==(StringView s1, String const& s2) {
  return s1.m_view.compare(s2.utf8()) == 0;
}

bool operator==(StringView s1, StringView s2) {
  return s1.m_view == s2.m_view;
}

bool operator!=(StringView s1, StringView s2) {
  return s1.m_view != s2.m_view;
}

bool operator<(StringView s1, StringView s2) {
  return s1.m_view < s2.m_view;
}

std::ostream& operator<<(std::ostream& os, StringView const& s) {
  os << s.utf8();
  return os;
}

}

fmt::appender fmt::formatter<Star::StringView>::format(Star::StringView const& s, format_context& ctx) const {
  return formatter<std::string_view>::format(s.utf8(), ctx);
};

#endif
