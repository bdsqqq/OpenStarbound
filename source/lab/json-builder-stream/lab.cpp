#include "StarJsonBuilder.hpp"
#include <cxxabi.h>
#include <cstring>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <typeinfo>
#include <vector>
#include <algorithm>

using namespace Star;

// Bytes are unsigned here; UTF32 event input is parsed independently below.
static std::string hex(std::string const& bytes) {
  static char const digits[] = "0123456789abcdef";
  std::string result;
  for (unsigned char b : bytes) { result += digits[b >> 4]; result += digits[b & 15]; }
  return result;
}
static std::string error(std::exception const& e) {
  int status = 0;
  std::unique_ptr<char, decltype(&std::free)> name(abi::__cxa_demangle(typeid(e).name(), nullptr, nullptr, &status), &std::free);
  return "E:" + std::string(status == 0 ? name.get() : typeid(e).name()) + ":" + hex(e.what());
}
static std::string typed(Json const& j, bool sorted) {
  switch (j.type()) {
    case Json::Type::Null: return "n";
    case Json::Type::Bool: return j.toBool() ? "b1" : "b0";
    case Json::Type::Int: return "i" + std::to_string(j.toInt());
    case Json::Type::Float: {
      double d = j.toDouble(); uint64_t bits; std::memcpy(&bits, &d, sizeof(bits));
      std::ostringstream out; out << 'f' << std::hex << std::setw(16) << std::setfill('0') << bits;
      return out.str();
    }
    case Json::Type::String: return "s" + hex(j.toString().utf8());
    case Json::Type::Array: {
      std::string out = "a["; bool first = true;
      for (auto const& v : j.iterateArray()) { if (!first) out += ','; first = false; out += typed(v, sorted); }
      return out + ']';
    }
    case Json::Type::Object: {
      std::vector<std::pair<std::string, Json>> pairs;
      for (auto const& p : j.iterateObject()) pairs.emplace_back(p.first.utf8(), p.second);
      if (sorted) std::sort(pairs.begin(), pairs.end(), [](auto const& a, auto const& b) { return a.first < b.first; });
      std::string out = "o{"; bool first = true;
      for (auto const& p : pairs) { if (!first) out += ','; first = false; out += hex(p.first) + ':' + typed(p.second, sorted); }
      return out + '}';
    }
  }
  throw std::runtime_error("unknown Json type");
}
static bool shared(Json const& a, Json const& b) {
  if (a.type() != b.type()) return false;
  switch (a.type()) {
    case Json::Type::String: return a.stringPtr() == b.stringPtr();
    case Json::Type::Array: return a.arrayPtr() == b.arrayPtr();
    case Json::Type::Object: return a.objectPtr() == b.objectPtr();
    default: return true;
  }
}
static std::string drain(JsonBuilderStream b, bool sorted) {
  std::string out; bool first = true;
  while (b.stackSize()) {
    if (!first) out += '|'; first = false;
    try { out += typed(b.takeTop(), sorted); }
    catch (std::exception const& e) { out += error(e); }
  }
  return out;
}
static bool lifecycle(JsonBuilderStream const& original) {
  JsonBuilderStream copy(original), assigned; assigned = original;
  JsonBuilderStream moved(std::move(copy)), movedAssigned; movedAssigned = std::move(assigned);
  if (drain(moved, false) != drain(movedAssigned, false)) return false;
  while (moved.stackSize()) {
    try {
      Json a = moved.takeTop(), b = movedAssigned.takeTop();
      if (!shared(a, b) || typed(a, false) != typed(b, false)) return false;
    } catch (std::exception const& a) {
      try { movedAssigned.takeTop(); return false; }
      catch (std::exception const& b) { if (error(a) != error(b)) return false; }
    }
  }
  return movedAssigned.stackSize() == 0;
}
int main() {
  // Base-pointer destruction is real native lifecycle exercise, not an OOM proof.
  std::unique_ptr<JsonStream> polymorphic(new JsonBuilderStream);
  std::string line, current;
  JsonBuilderStream builder;
  while (std::getline(std::cin, line)) {
    std::istringstream in(line); std::string name, index, op, payload;
    if (!std::getline(in,name,'\t') || !std::getline(in,index,'\t') || !std::getline(in,op,'\t') || !std::getline(in,payload)) return 2;
    if (name != current) { builder = JsonBuilderStream(); current = name; }
    std::vector<char32_t> units;
    if (payload != "-") { std::istringstream u(payload); std::string token; while (std::getline(u,token,',')) units.push_back(static_cast<char32_t>(std::stoul(token,nullptr,16))); }
    size_t len = units.size(); units.push_back(0); // valid storage even at length zero
    std::string result = "-", rawResult = "-";
    try {
      if (op == "BO") builder.beginObject();
      else if (op == "EO") builder.endObject();
      else if (op == "BA") builder.beginArray();
      else if (op == "EA") builder.endArray();
      else if (op == "K") builder.objectKey(units.data(),len);
      else if (op == "S") builder.putString(units.data(),len);
      else if (op == "I") builder.putInteger(units.data(),len);
      else if (op == "D") builder.putDouble(units.data(),len);
      else if (op == "B") builder.putBoolean(units.at(0) != 0);
      else if (op == "N") builder.putNull();
      else if (op == "W") builder.putWhitespace(units.data(),len);
      else if (op == "C") builder.putColon();
      else if (op == ",") builder.putComma();
      else if (op == "Z") {}
      else if (op == "T") { Json j = builder.takeTop(); result = typed(j,true); rawResult = typed(j,false); }
      else return 3;
    } catch (std::exception const& e) { result = rawResult = error(e); }
    std::cout << name << '\t' << index << '\t' << result << '\t' << builder.stackSize()
              << '\t' << drain(builder,true) << '\t' << (lifecycle(builder) ? 1 : 0)
              << '\t' << rawResult << '\t' << drain(builder,false) << '\n';
  }
}
