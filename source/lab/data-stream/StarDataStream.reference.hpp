#pragma once
#include "StarDataStream.hpp"

#include "StarString.hpp"
#include "StarNetCompatibility.hpp"

namespace Star {

extern unsigned const ReferenceCurrentStreamVersion;

// Writes complex types to bytes in a portable big-endian fashion.
class DataStreamReference {
public:
  DataStreamReference();
  virtual ~DataStreamReference() = default;

  // DataStream defaults to big-endian order for all primitive types
  ByteOrder byteOrder() const;
  void setByteOrder(ByteOrder byteOrder);

  // DataStream can optionally write strings as null terminated rather than
  // length prefixed
  bool nullTerminatedStrings() const;
  void setNullTerminatedStrings(bool nullTerminatedStrings);

  // streamCompatibilityVersion defaults to CurrentStreamVersion, but can be
  // changed for compatibility with older versions of DataStream serialization.
  unsigned streamCompatibilityVersion() const;
  void setStreamCompatibilityVersion(unsigned streamCompatibilityVersion);
  void setStreamCompatibilityVersion(NetCompatibilityRules const& rules);
  // Do direct reads and writes
  virtual void readData(char* data, size_t len) = 0;
  virtual void writeData(char const* data, size_t len) = 0;
  virtual bool atEnd() { return false; };

  // These do not read / write sizes, they simply read / write directly.
  ByteArray readBytes(size_t len);
  void writeBytes(ByteArray const& ba);

  DataStreamReference& operator<<(bool d);
  DataStreamReference& operator<<(char c);
  DataStreamReference& operator<<(int8_t d);
  DataStreamReference& operator<<(uint8_t d);
  DataStreamReference& operator<<(int16_t d);
  DataStreamReference& operator<<(uint16_t d);
  DataStreamReference& operator<<(int32_t d);
  DataStreamReference& operator<<(uint32_t d);
  DataStreamReference& operator<<(int64_t d);
  DataStreamReference& operator<<(uint64_t d);
  DataStreamReference& operator<<(float d);
  DataStreamReference& operator<<(double d);

  DataStreamReference& operator>>(bool& d);
  DataStreamReference& operator>>(char& c);
  DataStreamReference& operator>>(int8_t& d);
  DataStreamReference& operator>>(uint8_t& d);
  DataStreamReference& operator>>(int16_t& d);
  DataStreamReference& operator>>(uint16_t& d);
  DataStreamReference& operator>>(int32_t& d);
  DataStreamReference& operator>>(uint32_t& d);
  DataStreamReference& operator>>(int64_t& d);
  DataStreamReference& operator>>(uint64_t& d);
  DataStreamReference& operator>>(float& d);
  DataStreamReference& operator>>(double& d);

  // Writes and reads a VLQ encoded integer.  Can write / read anywhere from 1
  // to 10 bytes of data, with integers of smaller (absolute) value taking up
  // fewer bytes.  size_t version can be used to portably write a size_t type,
  // and portably and efficiently handles the case of NPos.

  size_t writeVlqU(uint64_t i);
  size_t writeVlqI(int64_t i);
  size_t writeVlqS(size_t i);

  size_t readVlqU(uint64_t& i);
  size_t readVlqI(int64_t& i);
  size_t readVlqS(size_t& i);

  uint64_t readVlqU();
  int64_t readVlqI();
  size_t readVlqS();

  // The following functions write / read data with length and then content
  // following, but note that the length is encoded as an unsigned VLQ integer.
  // String objects are encoded in utf8, and can optionally be written as null
  // terminated rather than length then content.

  DataStreamReference& operator<<(const char* s);
  DataStreamReference& operator<<(std::string const& d);
  DataStreamReference& operator<<(ByteArray const& d);
  DataStreamReference& operator<<(String const& s);

  DataStreamReference& operator>>(std::string& d);
  DataStreamReference& operator>>(ByteArray& d);
  DataStreamReference& operator>>(String& s);

  // All enum types are automatically serializable

  template <typename EnumType, typename = typename std::enable_if<std::is_enum<EnumType>::value>::type>
  DataStreamReference& operator<<(EnumType const& e);

  template <typename EnumType, typename = typename std::enable_if<std::is_enum<EnumType>::value>::type>
  DataStreamReference& operator>>(EnumType& e);

  // Convenience method to avoid temporary.
  template <typename T>
  T read();

  // Convenient argument style reading / writing

  template <typename Data>
  void read(Data& data);

  template <typename Data>
  void write(Data const& data);

  // Argument style reading / writing with casting.

  template <typename ReadType, typename Data>
  void cread(Data& data);

  template <typename WriteType, typename Data>
  void cwrite(Data const& data);

  // Argument style reading / writing of variable length integers.  Arguments
  // are explicitly casted, so things like enums are allowed.

  template <typename IntegralType>
  void vuread(IntegralType& data);

  template <typename IntegralType>
  void viread(IntegralType& data);

  template <typename IntegralType>
  void vsread(IntegralType& data);

  template <typename IntegralType>
  void vuwrite(IntegralType const& data);

  template <typename IntegralType>
  void viwrite(IntegralType const& data);

  template <typename IntegralType>
  void vswrite(IntegralType const& data);

  // Store a fixed point number as a variable length integer

  template <typename FloatType>
  void vfread(FloatType& data, FloatType base);

  template <typename FloatType>
  void vfwrite(FloatType const& data, FloatType base);

  // Read a shared / unique ptr, and store whether the pointer is initialized.

  template <typename PointerType, typename ReadFunction>
  void pread(PointerType& pointer, ReadFunction readFunction);

  template <typename PointerType, typename WriteFunction>
  void pwrite(PointerType const& pointer, WriteFunction writeFunction);

  template <typename PointerType>
  void pread(PointerType& pointer);

  template <typename PointerType>
  void pwrite(PointerType const& pointer);

  // WriteFunction should be void (DataStream& ds, Element const& e)
  template <typename Container, typename WriteFunction>
  void writeContainer(Container const& container, WriteFunction function);

  // ReadFunction should be void (DataStream& ds, Element& e)
  template <typename Container, typename ReadFunction>
  void readContainer(Container& container, ReadFunction function);

  template <typename Container, typename WriteFunction>
  void writeMapContainer(Container& map, WriteFunction function);

  // Specialization of readContainer for map types (whose elements are a pair
  // with the key type marked const)
  template <typename Container, typename ReadFunction>
  void readMapContainer(Container& map, ReadFunction function);

  template <typename Container>
  void writeContainer(Container const& container);

  template <typename Container>
  void readContainer(Container& container);

  template <typename Container>
  void writeMapContainer(Container const& container);

  template <typename Container>
  void readMapContainer(Container& container);

private:
  void writeStringData(char const* data, size_t len);

  ByteOrder m_byteOrder;
  bool m_nullTerminatedStrings;
  unsigned m_streamCompatibilityVersion;
};

template <typename EnumType, typename>
DataStreamReference& DataStreamReference::operator<<(EnumType const& e) {
  *this << (typename std::underlying_type<EnumType>::type)e;
  return *this;
}

template <typename EnumType, typename>
DataStreamReference& DataStreamReference::operator>>(EnumType& e) {
  typename std::underlying_type<EnumType>::type i;
  *this >> i;
  e = (EnumType)i;
  return *this;
}

template <typename T>
T DataStreamReference::read() {
  T t;
  *this >> t;
  return t;
}

template <typename Data>
void DataStreamReference::read(Data& data) {
  *this >> data;
}

template <typename Data>
void DataStreamReference::write(Data const& data) {
  *this << data;
}

template <typename ReadType, typename Data>
void DataStreamReference::cread(Data& data) {
  ReadType v;
  *this >> v;
  data = (Data)v;
}

template <typename WriteType, typename Data>
void DataStreamReference::cwrite(Data const& data) {
  WriteType v = (WriteType)data;
  *this << v;
}

template <typename IntegralType>
void DataStreamReference::vuread(IntegralType& data) {
  uint64_t i = readVlqU();
  data = (IntegralType)i;
}

template <typename IntegralType>
void DataStreamReference::viread(IntegralType& data) {
  int64_t i = readVlqI();
  data = (IntegralType)i;
}

template <typename IntegralType>
void DataStreamReference::vsread(IntegralType& data) {
  size_t s = readVlqS();
  data = (IntegralType)s;
}

template <typename IntegralType>
void DataStreamReference::vuwrite(IntegralType const& data) {
  writeVlqU((uint64_t)data);
}

template <typename IntegralType>
void DataStreamReference::viwrite(IntegralType const& data) {
  writeVlqI((int64_t)data);
}

template <typename IntegralType>
void DataStreamReference::vswrite(IntegralType const& data) {
  writeVlqS((size_t)data);
}

template <typename FloatType>
void DataStreamReference::vfread(FloatType& data, FloatType base) {
  int64_t i = readVlqI();
  data = (FloatType)i * base;
}

template <typename FloatType>
void DataStreamReference::vfwrite(FloatType const& data, FloatType base) {
  writeVlqI((int64_t)round(data / base));
}

template <typename PointerType, typename ReadFunction>
void DataStreamReference::pread(PointerType& pointer, ReadFunction readFunction) {
  bool initialized = read<bool>();
  if (initialized) {
    auto element = make_unique<typename std::decay<typename PointerType::element_type>::type>();
    readFunction(*this, *element);
    pointer.reset(element.release());
  } else {
    pointer.reset();
  }
}

template <typename PointerType, typename WriteFunction>
void DataStreamReference::pwrite(PointerType const& pointer, WriteFunction writeFunction) {
  if (pointer) {
    write(true);
    writeFunction(*this, *pointer);
  } else {
    write(false);
  }
}

template <typename PointerType>
void DataStreamReference::pread(PointerType& pointer) {
  return pread(pointer, [](DataStreamReference& ds, typename std::decay<typename PointerType::element_type>::type& value) {
      ds.read(value);
    });
}

template <typename PointerType>
void DataStreamReference::pwrite(PointerType const& pointer) {
  return pwrite(pointer, [](DataStreamReference& ds, typename std::decay<typename PointerType::element_type>::type const& value) {
      ds.write(value);
    });
}

template <typename Container, typename WriteFunction>
void DataStreamReference::writeContainer(Container const& container, WriteFunction function) {
  writeVlqU(container.size());
  for (auto const& elem : container)
    function(*this, elem);
}

template <typename Container, typename ReadFunction>
void DataStreamReference::readContainer(Container& container, ReadFunction function) {
  container.clear();
  size_t size = readVlqU();
  for (size_t i = 0; i < size; ++i) {
    typename Container::value_type elem;
    function(*this, elem);
    container.insert(container.end(), elem);
  }
}

template <typename Container, typename WriteFunction>
void DataStreamReference::writeMapContainer(Container& map, WriteFunction function) {
  writeVlqU(map.size());
  for (auto const& elem : map)
    function(*this, elem.first, elem.second);
}

template <typename Container, typename ReadFunction>
void DataStreamReference::readMapContainer(Container& map, ReadFunction function) {
  map.clear();
  size_t size = readVlqU();
  for (size_t i = 0; i < size; ++i) {
    typename Container::key_type key;
    typename Container::mapped_type mapped;
    function(*this, key, mapped);
    map.insert(make_pair(std::move(key), std::move(mapped)));
  }
}

template <typename Container>
void DataStreamReference::writeContainer(Container const& container) {
  writeContainer(container, [](DataStreamReference& ds, typename Container::value_type const& element) { ds << element; });
}

template <typename Container>
void DataStreamReference::readContainer(Container& container) {
  readContainer(container, [](DataStreamReference& ds, typename Container::value_type& element) { ds >> element; });
}

template <typename Container>
void DataStreamReference::writeMapContainer(Container const& container) {
  writeMapContainer(container, [](DataStreamReference& ds, typename Container::key_type const& key, typename Container::mapped_type const& mapped) {
      ds << key;
      ds << mapped;
    });
}

template <typename Container>
void DataStreamReference::readMapContainer(Container& container) {
  readMapContainer(container, [](DataStreamReference& ds, typename Container::key_type& key, typename Container::mapped_type& mapped) {
      ds >> key;
      ds >> mapped;
    });
}

}
