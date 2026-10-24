// Diagnostic-only ARM policy candidate for the isolated emitted instructions.
// Not a production patch and not a complete lighting backend.
#[no_mangle]
pub unsafe extern "C" fn policy_spread(src: *const f32,dst: *const f32,drop:f32,out:*mut f32) {
 let s=std::slice::from_raw_parts(src,3);let d=std::slice::from_raw_parts(dst,3);
 let m=s[0].max(s[1].max(s[2]));let q=drop/m;
 for i in 0..3 { *out.add(i)=if m<=0. {d[i]} else {(-s[i]).mul_add(q,s[i]).max(d[i])}; }
}
#[no_mangle]
pub unsafe extern "C" fn policy_subtract(src:*const f32,drop:f32,out:*mut f32) {
 let s=std::slice::from_raw_parts(src,3);let m=s[0].max(s[1]).max(s[2]);let r=1.0/m;
 for i in 0..3 {let p=(drop*s[i])*r;*out.add(i)=if m<=0. {s[i]} else if s[i]>p {s[i]-p} else {0.};}
}
#[no_mangle]
pub extern "C" fn policy_distance(x:f32,y:f32)->f32 {y.mul_add(y,x*x).sqrt()}
#[no_mangle]
pub extern "C" fn policy_circular(obs:f32,dir:f32)->f32 {1.0/(obs*dir)}
#[no_mangle]
pub extern "C" fn policy_diag(air:f32)->f32 {((1.0_f32/air) as f64*std::f64::consts::SQRT_2) as f32}
#[no_mangle]
pub unsafe extern "C" fn policy_source(x:f32,y:f32,att:f32,out:*mut f32) {
 *out=att*(x+y);*out.add(1)=att*((x+1.)-y);*out.add(2)=att*((y-1.)+(2.-x));*out.add(3)=att*((2.-x)-y);
}
#[no_mangle]
pub unsafe extern "C" fn policy_direction(x:f32,y:f32,d:f32,out:*mut f32) {*out=x/d;*out.add(1)=y/d;}
