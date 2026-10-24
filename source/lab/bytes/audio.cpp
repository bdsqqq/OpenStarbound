#include "StarAudio.hpp"
#include "StarBuffer.hpp"
#ifdef STAR_USE_RUST_BYTES
#include "StarRustBytes.h"
#endif
#include <iostream>
#include <array>
#include <string>
using namespace Star;
static std::array<uint64_t,6> counts() {
  std::array<uint64_t,6> r{};
#ifdef STAR_USE_RUST_BYTES
  for (unsigned i=0;i<6;++i) r[i]=star_bytes_call_count(i);
#endif
  return r;
}
int main(int argc, char**) {
  // Independently specified bytes, never encoded through the candidate.
  const unsigned char wav[]={0x52,0x49,0x46,0x46,0x34,0,0,0,0x57,0x41,0x56,0x45,0x66,0x6d,0x74,0x20,0x10,0,0,0,1,0,1,0,0x40,0x1f,0,0,0x80,0x3e,0,0,2,0,0x10,0,0x64,0x61,0x74,0x61,0x10,0,0,0,0,0x80,0xc7,0xcf,0xff,0xff,0,0,1,0,0x39,0x30,0xff,0x7f,0,0};
  auto device=make_shared<Buffer>(ByteArray((char const*)wav,sizeof(wav)));
  auto before=counts();
  Audio audio(device,"byteslab.wav");
  int16_t pcm[10]{};
  auto n=audio.read(pcm,10);
  auto eof=audio.read(pcm+8,1);
  auto end=audio.currentSample();
  auto after=counts();
  const int16_t expected[]={-32768,-12345,-1,0,1,12345,32767,0};
  bool ok=audio.channels()==1 && audio.sampleRate()==8000 && audio.totalSamples()==8 && !audio.compressed() && n==8 && eof==0 && end==8 && audio.currentTime()==0.001;
  for(unsigned i=0;i<8;++i) ok &= pcm[i]==expected[i]+(argc>1 && i==1 ? 1:0);
  std::array<uint64_t,6> delta{};
  for(unsigned i=0;i<6;++i) {
    delta[i]=after[i]-before[i];
#ifdef STAR_USE_RUST_BYTES
    ok &= delta[i]==(i==4 ? 17:0);
#else
    ok &= delta[i]==0;
#endif
  }
  audio.seekSample(3);
  int16_t sought[3]{};
  ok &= audio.currentSample()==3 && audio.read(sought,3)==3 && sought[0]==0 && sought[1]==1 && sought[2]==12345 && audio.currentSample()==6;
  audio.seekSample(8); ok &= audio.read(sought,3)==0 && audio.currentSample()==8;
  std::cout<<"{\"channels\":"<<audio.channels()<<",\"rate\":"<<audio.sampleRate()<<",\"samples\":"<<audio.totalSamples()<<",\"read\":"<<n<<",\"eof\":"<<eof<<",\"end\":"<<end<<",\"pcm\":[";
  for(unsigned i=0;i<8;++i) std::cout<<(i?",":"")<<pcm[i];
  std::cout<<"],\"receipts\":[";
  for(unsigned i=0;i<6;++i) std::cout<<(i?",":"")<<delta[i];
  std::cout<<"],\"seek_verified\":"<<(ok?"true":"false")<<"}\n";
  if(!ok) {std::cerr<<"COMPARISON pcm/metadata/end/seek/receipt mismatch\n";return 1;}
}
