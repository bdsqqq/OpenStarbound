#pragma once

#include "StarRustJsonPatch.h"
#include "StarJsonPatch.hpp"
#include "StarJsonPath.hpp"
#include <optional>
#include <exception>
#include <limits>

namespace Star {
namespace JsonPatchHostDetail {
struct Context {
  std::optional<Json> B, Op, Value, Searchable, SearchValue, TestValue, Result;
  std::optional<Maybe<Json>> OptionalValue;
  std::optional<String> Path, Operation;
  std::optional<JsonPath::Pointer> To, From;
  std::optional<JsonArray> MatchArray;
  JsonArray const* Patch=nullptr;
  JsonPath::Pointer* ExternalFindPointer=nullptr;
  std::exception_ptr Pending;
  uint32_t PendingClass=0;
};
inline uint32_t classify() noexcept {
  try { throw; }
  catch(JsonPath::TraversalException const&) {return JP_TRAVERSAL;}
  catch(JsonException const&) {return JP_JSON;}
  catch(MapException const&) {return JP_MAP;}
  catch(JsonPatchTestFail const&) {return JP_TEST_FAIL;}
  catch(...) {return JP_OTHER;}
}
static JsonPath::Pointer* pointer(Context& c,uint32_t p) noexcept {
  if(p==0)return c.To?&*c.To:nullptr;
  if(p==1)return c.From?&*c.From:nullptr;
  if(p==2)return c.ExternalFindPointer;
  return nullptr;
}
inline uint32_t host(void* raw,uint32_t op,uint32_t a,uint32_t b,uint64_t n,uint64_t* out) noexcept {
  if(!raw||!out||reinterpret_cast<uintptr_t>(out)%alignof(uint64_t)||reinterpret_cast<uintptr_t>(out)>UINTPTR_MAX-sizeof(uint64_t)||op>41)return JP_HOST_ABI_INVALID;
  auto& c=*static_cast<Context*>(raw);
  bool indexed=op==1||op==19||(op>=24&&op<=28)||op==31||op==32;
  if((!indexed&&n)|| (op!=11&&op!=35&&op!=36&&op!=38&&a)|| (op!=35&&op!=38&&b))return JP_HOST_ABI_INVALID;
  if(op==11&&a>2)return JP_HOST_ABI_INVALID;
  if(op==35&&(a>6||(a==0?b>2:b!=0)))return JP_HOST_ABI_INVALID;
  if(op==36&&a>1)return JP_HOST_ABI_INVALID;
  if(op==38&&(a>9||b>2))return JP_HOST_ABI_INVALID;
  bool cleanup=op>=39, exceptional=op==35||op==36||op==37||op==38||cleanup;
  if(c.Pending&&!exceptional)return JP_HOST_ABI_INVALID;
  if(op==35&&((a==5&&c.PendingClass!=JP_TRAVERSAL)||(a==6&&c.PendingClass!=JP_MAP)||(a!=5&&a!=6&&c.Pending)))return JP_HOST_ABI_INVALID;
  if(op==36&&(!c.Pending||(c.PendingClass!=JP_JSON&&c.PendingClass!=JP_TRAVERSAL)))return JP_HOST_ABI_INVALID;
  if(op==37&&(!c.Pending||c.PendingClass!=JP_TRAVERSAL))return JP_HOST_ABI_INVALID;
  if(op==38&&((b==1&&c.Pending)||(b==2&&!c.Pending)))return JP_HOST_ABI_INVALID;
  // Validate typed scratch fields before any native semantic operation.
  bool valid=true;
  switch(op){
    case 0:case 1:valid=c.Patch;break;
    case 2:valid=bool(c.Operation);break;
    case 3:case 4:case 5:case 7:case 8:case 9:case 10:case 12:case 13:valid=bool(c.Op);break;
    case 6:valid=bool(c.Path);break;
    case 11:valid=c.B&&pointer(c,a);break;
    case 14:valid=c.B&&c.To;break;
    case 15:valid=c.OptionalValue&&c.TestValue;break;
    case 16:case 17:valid=bool(c.Searchable);break;
    case 18:valid=bool(c.MatchArray);break;
    case 19:valid=c.MatchArray&&c.SearchValue;break;
    case 20:valid=bool(c.B);break;
    case 21:valid=c.B&&c.To;break;
    case 22:case 23:case 25:case 26:valid=c.B&&c.To&&c.Value;break;
    case 24:case 27:case 31:case 32:valid=c.B&&c.To&&c.Searchable;break;
    case 28:valid=c.Result&&c.From&&c.Searchable;break;
    case 29:valid=c.B&&c.From;break;
    case 30:valid=c.B&&c.To&&c.From&&c.Value;break;
    case 33:valid=c.B&&c.To&&c.Op;break;
    case 34:valid=bool(c.Result);break;
    case 35:switch(a){case 0:valid=pointer(c,b);break;case 1:case 2:valid=bool(c.SearchValue);break;case 3:valid=bool(c.Path);break;case 4:valid=c.OptionalValue&&c.TestValue;break;case 6:valid=bool(c.Op);break;}break;
  }
  if(op==32&&!c.Op)valid=false;
  if(!valid)return JP_HOST_ABI_INVALID;
  if(op==1&&n>=c.Patch->size())return JP_HOST_ABI_INVALID;
  if(op==19&&n>=c.MatchArray->size())return JP_HOST_ABI_INVALID;
  if((op>=24&&op<=28)||op==31||op==32){if(!c.Searchable||!c.Searchable->isType(Json::Type::Array)||n>=c.Searchable->size())return JP_HOST_ABI_INVALID;}
  try {
    switch(op){
    case 0:*out=c.Patch->size();break;
    case 1:c.Op=(*c.Patch)[n];break;
    case 2:{static StringMap<uint32_t> const map{{"test",3},{"remove",4},{"add",5},{"replace",6},{"move",7},{"copy",8},{"merge",9}};*out=map.get(*c.Operation);break;}
    case 3:c.Operation=c.Op->getString("op");break;
    case 4:c.Path=c.Op->getString("path");break;
    case 5:c.Value=c.Op->get("value");break;
    case 6:c.To.emplace(*c.Path);break;
    case 7:c.To.emplace(c.Op->getString("path"));break;
    case 8:c.From.emplace(c.Op->getString("from"));break;
    case 9:*out=c.Op->getBool("inverse",false);break;
    case 10:*out=c.Op->contains("search");break;
    case 11:c.Searchable=pointer(c,a)->get(*c.B);break;
    case 12:c.SearchValue=c.Op->get("search");break;
    case 13:c.OptionalValue=c.Op->opt("value");*out=bool(*c.OptionalValue);break;
    case 14:c.TestValue=c.To->get(*c.B);break;
    case 15:*out=*c.OptionalValue&&(*c.TestValue==**c.OptionalValue);break;
    case 16:*out=c.Searchable->isType(Json::Type::Array);break;
    case 17:c.MatchArray=c.Searchable->toArray();break;
    case 18:*out=c.MatchArray->size();break;
    case 19:*out=jsonPartialMatch((*c.MatchArray)[n],*c.SearchValue);break;
    case 20:c.Result=*c.B;break;
    case 21:c.Result=c.To->remove(*c.B);break;
    case 22:c.Result=c.To->add(*c.B,*c.Value);break;
    case 23:c.Result=c.To->add(c.To->remove(*c.B),*c.Value);break;
    case 24:c.Result=c.To->add(c.To->remove(*c.B),c.Searchable->eraseIndex(n));break;
    case 25:c.Result=c.To->add(c.To->remove(*c.B),c.Searchable->insert(n,*c.Value));break;
    case 26:c.Result=c.To->add(c.To->remove(*c.B),c.Searchable->set(n,*c.Value));break;
    case 27:c.Result=c.To->add(*c.B,c.Searchable->get(n));break;
    case 28:c.Result=c.From->add(*c.Result,c.Searchable->eraseIndex(n));break;
    case 29:c.Value=c.From->get(*c.B);break;
    case 30:c.Result=c.To->add(c.From->remove(*c.B),*c.Value);break;
    case 31:c.Result=c.To->add(*c.B,c.Searchable->get(n));break;
    case 32:c.Result=c.To->add(c.To->remove(*c.B),c.Searchable->set(n,jsonMerge(c.Searchable->get(n),c.Op->get("value"))));break;
    case 33:c.Result=c.To->add(c.To->remove(*c.B),jsonMerge(c.To->get(*c.B),c.Op->get("value")));break;
    case 34:c.B=*c.Result;break;
    case 35:switch(a){
      case 0:throw JsonPatchException(strf("Search operation failure, value at '{}' is not an array.",pointer(c,b)->path()),false);
      case 1:throw JsonPatchTestFail(strf("Test operation failure, expected {} to be missing.",*c.SearchValue),false);
      case 2:throw JsonPatchTestFail(strf("Test operation failure, could not find {}.",*c.SearchValue),false);
      case 3:throw JsonPatchTestFail(strf("Test operation failure, expected {} to be missing.",*c.Path),false);
      case 4:throw JsonPatchTestFail(strf("Test operation failure, expected {} found {}.",*c.OptionalValue,*c.TestValue),false);
      case 5:try{std::rethrow_exception(c.Pending);}catch(JsonPath::TraversalException const& e){throw JsonPatchTestFail(strf("Test operation failure: {}",e.what()),false);}
      case 6:throw JsonPatchException(strf("Invalid operation: {}",c.Op->getString("op")),false);
    }break;
    case 36:try{std::rethrow_exception(c.Pending);}catch(JsonException const&e){throw JsonPatchException(strf(a==0?"Could not apply operation to base. {}":"Could not apply patch to base. {}",e.what()),false);}break;
    case 37:c.Pending={};c.PendingClass=0;break;
    case 38:break;
    case 39:c.MatchArray.reset();break;
    case 40:c.Value.reset();c.Searchable.reset();c.SearchValue.reset();c.TestValue.reset();c.OptionalValue.reset();c.Path.reset();c.To.reset();c.From.reset();c.MatchArray.reset();break;
    case 41:c.Operation.reset();break;
    }
    return JP_OK;
  } catch(...) {c.Pending=std::current_exception();return c.PendingClass=classify();}
}

inline Context operationContext(Json const& base, Json const& operation) {
  Context c;
  c.B = base;
  c.Op = operation;
  return c;
}

// Rust owns control flow; native values and the exact exception object never
// leave this context. An aborted controller must never retry the C++ algorithm.
inline uint64_t invoke(uint32_t entry, Context& c) {
  uint64_t scalar = 0;
  auto status = star_json_patch_run(entry, host, &c, &scalar);
  if (status == JP_NATIVE_EXCEPTION_PENDING && c.Pending)
    std::rethrow_exception(c.Pending);
  if (status != JP_SUCCESS || c.Pending)
    throw StarException("Rust Json patch controller failed", false);
  return scalar;
}

inline Json operation(uint32_t entry, Json const& base, Json const& op) {
  auto c = operationContext(base, op);
  invoke(entry, c);
  if (!c.Result)
    throw StarException("Rust Json patch controller omitted its result", false);
  return std::move(*c.Result);
}
}
}
