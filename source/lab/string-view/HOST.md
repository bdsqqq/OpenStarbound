# native StringView host prototype

Native-only, unchanged public header and original 58 compiled definitions.
Mode numbers are source-map id minus one. Controller owns scalar branches,
UTF iterator search loops, comparison sequencing, boundary walks and split
sequencing. Native context owns views, iterator slots, typed outputs, references,
formatting and the original exception_ptr. ByteArray allocation stays in the
original wrapper return expression (no optional-result move); substring return
retains the pointer/length constructor, and callback substr temporaries preserve
the original rvalue conversion category. No pointer travels as an
integer through the ABI. Native byte find/find_first_of remain library leaves.

String constructor/operator+= bridges preserve const-reference versus lvalue
std::string_view argument categories in the original native full expressions.
StringView constructors preserve the original m_view initializers. Constructor
and String bridge controller counters measure routing, not allocation completion.
Private comparison calls within other controllers record slot48 attempts/results;
the standalone private wrapper uses the same comparison body without double count.

Terminal split callback can delete its receiver: callback arguments are formed
before invocation, and FINISH examines only the surviving stack context. Neither
FINISH nor wrapper teardown dereferences the receiver. Span exclusions use local
uintptr arithmetic with representational-overflow rejection, never arithmetic
on an unknown output pointer; this is not arbitrary-pointer validation. Nonterminal callbacks
reread the live receiver next iteration; pattern view is a by-value copy.

Status0 succeeds,1 preserves pending native exception,2 rejects protocol,3 is
C++-prototype-only containment for an illegally throwing callback. Native callback
catches all native exceptions; wrapper rethrows after controller return. The
status3 test MUST NOT be carried into a Rust test. TLS counters wrap unsigned64,
58x3 attempts/success/pending; null context/host and invalid modes are uncounted.

Run fresh (never overwrite a previous trial):

```
python3 -B source/lab/string-view/host_run.py run --output build/string-view-lab/host-prototype-r1/trial1
python3 -B source/lab/string-view/host_run.py verify --output build/string-view-lab/host-prototype-r1/trial1
```

The runner binds original parent113-object closure, compiler/flags/libraries,
exact owned files and discovered dependencies before/after; it replaces index92
only, with unchanged production header. It freezes before compile/execution.
Expected8332 rows remain the original independent oracle. Audit counters must be
positive/balanced for every slot. A normally exiting native bypass emits identical
values but zero controller counts and must fail the execution gate. Native-only
protocol tests cover malformed roles/ops/output/context, TLS, exception identity
and callback containment. Original parent calibration remains immutable.

This is finite native prototype evidence only. Parent owns the independent
callback deletion supplement, full-expression review and integration. No Rust,
CMake, game, production change, commits, or full-module/application claim.
