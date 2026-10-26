#pragma once
#include "StarStringView.hpp"
#include "host_api.h"
#include <exception>
#include <optional>
namespace Star::StringViewHost {
// The public header is unchanged. Only member definitions bind private m_view.
struct Ctx {
  uint32_t mode=58;
  std::string_view const* view=nullptr;
  std::string_view* mutableView=nullptr;
  std::string_view pattern{};
  uint64_t args[6]={};
  uint64_t result=0;
  int comparison=0;
  std::exception_ptr pending;
  std::optional<StringView::const_iterator> iter[4];
  unsigned roles[4]={};
  std::optional<StringView::const_iterator> iteratorResult;
  std::string_view viewResult{};
  char const* pointerResult=nullptr;
  StringView::SplitCallback* callback=nullptr;
  char const* cstring=nullptr;
  std::string const* string=nullptr;
  String const* starString=nullptr;
  std::ostream* stream=nullptr;
  fmt::formatter<std::string_view> const* formatter=nullptr;
  fmt::format_context* formatContext=nullptr;
  std::optional<fmt::appender> appender;
};
uint32_t host(void*,uint32_t,uint64_t,uint64_t,uint64_t,uint64_t*) noexcept;
void execute(uint32_t,Ctx&);
// Preserve reference category in the original native full expression. The
// controller never receives the string object or performs its allocation.
template<class T> T& bridge(uint32_t mode,T& value) {
  Ctx c; execute(mode,c); return value;
}
}
