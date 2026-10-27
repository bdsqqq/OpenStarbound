// Protocol breadth only: these callbacks are not cache or actual-clock proof.
namespace ActualRustProtocol {
struct Loop { uint64_t remaining=350001; bool appended=false; };
uint32_t looping(void* raw,SbTtlRequest const* q,SbTtlReply* out) noexcept {
 auto& s=*static_cast<Loop*>(raw);
 if(!q || !out || q->size!=24 || q->version!=1 || q->reserved || q->arg)return SB_TTL_INVALID;
 SbTtlReply r{24,1,SB_TTL_VOID,0,0};
 switch(q->op){
 case SB_TTL_VALUES_END:r.tag=SB_TTL_BOOL;r.value=s.remaining==0;break;
 case SB_TTL_VALUES_APPEND:if(s.appended || !s.remaining)return 2;s.appended=true;break;
 case SB_TTL_VALUES_NEXT:if(!s.appended || !s.remaining)return 2;s.appended=false;--s.remaining;break;
 default:return 2;
 }
 *out=r;return 0;
}
uint32_t nesting(void* raw,SbTtlRequest const* q,SbTtlReply* out) noexcept {
 if(!raw || !q || !out || q->size!=24 || q->version!=1 || q->reserved || q->arg || q->op!=SB_TTL_SET_EXPRESSION)return 2;
 auto& depth=*static_cast<unsigned*>(raw);
 if(depth){--depth;SbTtlReply nested{24,1,99,0,123};auto status=sb_ttl_run(SB_TTL_SET,SB_TTL_ROOT,raw,nesting,&nested);if(status)return status;}
 *out={24,1,SB_TTL_VOID,0,0};return 0;
}
void run(){
 using TtlControls::check;
 static_assert(sizeof(SbTtlRequest)==24 && sizeof(SbTtlReply)==24);
 static_assert(alignof(SbTtlRequest)==8 && alignof(SbTtlReply)==8);
 static_assert(offsetof(SbTtlRequest,arg)==16 && offsetof(SbTtlReply,value)==16);
 static_assert(SB_TTL_ABI_VERSION==1);
 Loop loop;SbTtlReply out{24,1,99,0,123};
 check("actual-rust-350001-values-no-cap",sb_ttl_run(SB_TTL_VALUES,SB_TTL_VALUE_LOOP,&loop,looping,&out)==0 && loop.remaining==0 && !loop.appended && out.tag==SB_TTL_VOID);
 unsigned depth=193;out={24,1,99,0,123};
 check("actual-rust-193-nested-no-cap",sb_ttl_run(SB_TTL_SET,SB_TTL_ROOT,&depth,nesting,&out)==0 && depth==0 && out.tag==SB_TTL_VOID);
 for(unsigned i=0;i<3;++i){SbTtlReply r{24,1,99,0,123};if(i==0)r.size=23;if(i==1)r.version=2;if(i==2)r.reserved=1;auto saved=r;
 check("actual-rust-invalid-caller-metadata-preserved",sb_ttl_run(SB_TTL_VALUES,SB_TTL_VALUE_LOOP,&loop,looping,&r)==2 && !std::memcmp(&saved,&r,24));}
 check("actual-rust-invalid-counter-coordinates",sb_ttl_count(19,0)==0 && sb_ttl_count(0,4)==0);
}
}
