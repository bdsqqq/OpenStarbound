# disjoint observation — not a native continuation permit

`allocation.py` observes archive, active root and outside storage directly in ONE
traversal. subtracting three separate overlapping walks can attribute deleted
active-root temporaries to outside storage. the isolated old-function fixture
reproduces that susceptibility; it does NOT identify the648e incident's cause.

fixed caps remain archive16gib/live4gib/active1536mib and outside+1536mib reserve.
inodes count once per category; cross-category hardlinks and traversal failures
reject with category totals and observation interval. symlink targets are never
followed. existing path-fixture fifos are charged as inode metadata, never opened
or consumed; unsupported sockets/devices reject. this remains a non-atomic
observation of a changing filesystem.

14 tests pass: old subtractive false rejection, direct outside invariant, genuine
outside growth/cap negatives, hardlink/alias/traversal/type controls. initial
actual scan rejected a legitimate historical fifo; that failure and source were
retained before adding metadata-only fifo support, not deleting fixtures.
actual22:38 scan passes: archive16,844,328,960/outside2,679,869,440/active224,235,520
bytes, with seven fifos untouched. all budgets/reservation remain unchanged.

completion `build/id-map-allocation-r1/completion.json`, sha256
`e7a6c19cd299cf50d9af388f91d6d94c60a5f9b25d3ae717a5a5a2ede1387d6f`.

original admission648e and its failed controller remain immutable and EXPIRED.
this helper is NOT retroactively substituted into it. reference six and candidate
two successful phases remain evidence, not a complete pair. no new native command
or old-deadline renewal occurred; game qualification and all39 remain open.
