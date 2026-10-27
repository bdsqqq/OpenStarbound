#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <typeinfo>
#include <type_traits>
#include LAB_HEADER

struct ProbeError : std::runtime_error { using std::runtime_error::runtime_error; };
struct Context {
  std::vector<uint32_t> out;
  std::vector<std::string> log;
  std::function<void()> callback;
  char failure = '-';
  long failureAt = -1, callbackAt = -1;
  size_t assignments = 0, increments = 0;
  bool failed = false, called = false;
};
static std::string hx(uint32_t c) { std::ostringstream s; s << std::hex << c; return s.str(); }
struct Probe {
  std::shared_ptr<Context> c;
  size_t position = 0;
  struct Ref {
    std::shared_ptr<Context> c;
    size_t position;
    mutable long attempt = -1;
    ~Ref() noexcept(false) {
      if(c->failure=='d') {
        c->log.push_back("D:"+std::to_string(position));
        if(!c->failed && attempt==c->failureAt) {
          c->failed=true;throw ProbeError("destructor");
        }
      }
    }
    void operator=(char32_t value) const {
      c->log.push_back("A:"+hx(value)+":"+std::to_string(position));
      size_t n=c->assignments++;attempt=long(n);
      if (!c->failed && c->failure=='a' && long(n)==c->failureAt) {
        c->failed=true;throw ProbeError("assignment");
      }
      c->out.push_back(value);
      if (!c->called && long(n)==c->callbackAt && c->callback) {
        c->called=true;c->callback();
      }
    }
  };
  Ref operator*() const { return {c,position}; }
  Probe& operator++() {
    c->log.push_back("I:"+std::to_string(position));
    size_t n=c->increments++;
    if (!c->failed && c->failure=='i' && long(n)==c->failureAt) {
      c->failed=true;throw ProbeError("increment");
    }
    ++position;return *this;
  }
  Probe operator++(int) { auto old=*this; ++*this; return old; }
};
static std::vector<std::string> split(std::string const& text,char by) {
  std::vector<std::string> parts;std::string part;std::istringstream in(text);
  while(std::getline(in,part,by))parts.push_back(part);
  return parts;
}
static std::string bytes(std::string const& s) {
  std::ostringstream out;out<<std::hex<<std::setfill('0');
  for(unsigned char c:s)out<<std::setw(2)<<unsigned(c);
  return out.str();
}
template<class Out>
void run(std::vector<std::string> const& row,std::string const& mode,Out out,
         std::shared_ptr<Context> c,std::vector<char32_t> const* wide,std::vector<char> const* narrow) {
  using Writer=Star::JsonWriter<Out>;
  static_assert(std::is_copy_constructible<Writer>::value && std::is_move_constructible<Writer>::value,"native construction");
  static_assert(std::is_copy_assignable<Writer>::value && std::is_move_assignable<Writer>::value,"native assignment");
  static_assert(std::has_virtual_destructor<Writer>::value,"native virtual destruction");
  std::unique_ptr<Writer> ws[2];ws[0]=std::make_unique<Writer>(out,std::stoul(row[1]));
  int active=0;std::vector<char32_t> data;
  c->failure=row[2][0];c->failureAt=std::stol(row[3]);c->callbackAt=std::stol(row[5]);
  char cb=row[4][0];size_t mi=std::stoul(row[6]);
  c->callback=[&]{
    c->log.push_back(std::string("CB:")+cb);
    if(cb=='m') { if(mi<data.size())data[mi]=0x5a; }
    else if(cb=='r')ws[active]->putBoolean(false);
    else if(cb=='n') { Writer nested(out,std::stoul(row[1]));nested.putNull(); }
    else if(cb=='e')ws[active]->endArray();
    else if(cb=='b')ws[active]->beginObject();
    // Ref owns a shared context and a value position, so replacing m_out
    // cannot invalidate the active proxy. The outer ++ then uses NEW m_out.
    else if(cb=='x')*ws[active]=Writer(out,7);
  };
  auto events=split(row[7],';');
  for(size_t i=0;i<events.size();++i) {
    std::string error="-",what="-";
    try {
      auto const& event=events[i];
      if(event=="COPY")ws[1]=std::make_unique<Writer>(*ws[active]);
      else if(event=="MOVE")ws[1]=std::make_unique<Writer>(std::move(*ws[0]));
      else if(event=="ASSIGN")*ws[0]=*ws[1];
      else if(event=="USE0")active=0;
      else if(event=="USE1")active=1;
      else {
        data.clear();auto colon=event.find(':');
        if(colon!=std::string::npos)for(auto const& n:split(event.substr(colon+1),','))data.push_back(std::stoul(n,nullptr,16));
        // Both first read and the final lookahead are part of the native
        // contract. Never use null, empty backing storage or an OOB sentinel.
        size_t len=data.size();data.push_back(0xabc);
        Writer& w=*ws[active];
        switch(event[0]) {
          case 'B':w.beginObject();break; case 'E':w.endObject();break;
          case 'A':w.beginArray();break; case 'Z':w.endArray();break;
          case 'K':w.objectKey(data.data(),len);break;case 'S':w.putString(data.data(),len);break;
          case 'D':w.putDouble(data.data(),len);break;case 'I':w.putInteger(data.data(),len);break;
          case 'W':w.putWhitespace(data.data(),len);break;
          case 'T':w.putBoolean(true);break;case 'F':w.putBoolean(false);break;
          case 'N':w.putNull();break;case 'C':w.putColon();break;case 'Q':w.putComma();break;
          default:throw std::logic_error("unknown event");
        }
      }
    } catch(Star::UnicodeException const& e) {
      if(typeid(e)!=typeid(Star::UnicodeException))throw;
      error="Star::UnicodeException";what=bytes(e.what());
    } catch(ProbeError const& e) {
      if(typeid(e)!=typeid(ProbeError))throw;
      error="ProbeError";what=bytes(e.what());
    }
    std::ostringstream output;output<<std::hex<<std::setfill('0');
    if(wide)for(char32_t v:*wide)output<<std::setw(8)<<uint32_t(v);
    else if(narrow)for(unsigned char v:*narrow)output<<std::setw(2)<<unsigned(v);
    else for(uint32_t v:c->out)output<<std::setw(mode=="p8"?2:8)<<v;
    std::ostringstream log;for(size_t n=0;n<c->log.size();++n){if(n)log<<',';log<<c->log[n];}
    std::cout<<row[0]<<'\t'<<mode<<'\t'<<i<<'\t'<<output.str()<<'\t'<<log.str()<<'\t'<<error<<'\t'<<what<<'\n';
  }
  // Callback references must be gone before local writer/input destruction.
  c->callback={};
}
int main() {
  std::string line;
  while(std::getline(std::cin,line)) {
    auto row=split(line,'\t');if(row.size()!=8)throw std::logic_error("row shape");
    {
      std::vector<char32_t> out;
      run(row,"u32",std::back_inserter(out),std::make_shared<Context>(),&out,nullptr);
    }
    {
      std::vector<char> out;
      run(row,"u8",Star::Utf8OutputIterator<std::back_insert_iterator<std::vector<char>>>(std::back_inserter(out)),std::make_shared<Context>(),nullptr,&out);
    }
    {
      auto c=std::make_shared<Context>();run(row,"p32",Probe{c},c,nullptr,nullptr);
    }
    {
      auto c=std::make_shared<Context>();run(row,"p8",Star::Utf8OutputIterator<Probe>(Probe{c}),c,nullptr,nullptr);
    }
  }
}
