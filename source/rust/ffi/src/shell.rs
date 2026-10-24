use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarShellClassify = unsafe extern "C" fn(*mut c_void, u32, *mut u32) -> i32;
pub type StarShellEmit = unsafe extern "C" fn(*mut c_void, u32, u32) -> i32;
thread_local! { static CALLS: Cell<u64> = const { Cell::new(0) }; }
#[no_mangle]
pub extern "C" fn star_shell_call_count() -> u64 {
    CALLS.with(Cell::get)
}
fn space(cp: u32) -> bool {
    matches!(cp, 0x20 | 9 | 10 | 13 | 0xfeff)
}
fn lead(cp: u32) -> bool {
    (0xd800..=0xdbff).contains(&cp)
}
fn nibble(cp: u32) -> u32 {
    match cp {
        48..=57 => cp - 48,
        65..=70 => cp - 65 + 10,
        97..=102 => cp - 97 + 10,
        _ => 0,
    }
}
struct Parser {
    input: *const u32,
    len: usize,
    pos: usize,
    quote: u32,
    count: usize,
    classify: StarShellClassify,
    emit: StarShellEmit,
    ctx: *mut c_void,
}
impl Parser {
    // Raw reads are deliberate: a foreign callback may change future input.
    unsafe fn current(&self) -> Option<u32> {
        if self.pos < self.len {
            Some(self.input.add(self.pos).read())
        } else {
            None
        }
    }
    unsafe fn next(&mut self) -> Option<u32> {
        if self.pos < self.len {
            self.pos += 1;
        }
        self.current()
    }
    fn previous(&mut self) {
        self.pos = self.pos.saturating_sub(1);
    }
    unsafe fn unicode(&mut self, previous: Option<u32>) -> Result<u32, ()> {
        // Preserve the legacy shadowed outer letter: the loop tests the initial
        // 'u', not each digit, so whitespace is consumed then classified.
        let initial = self.current().unwrap();
        let mut value = 0;
        let mut digits = 0;
        while !space(initial) && digits < 4 {
            let Some(cp) = self.next() else { break };
            let mut accepted = 0;
            if (self.classify)(self.ctx, cp, &mut accepted) != 0 {
                return Err(());
            }
            if accepted == 0 {
                return Ok(0xfffd);
            }
            value = (value << 4) | nibble(cp);
            digits += 1;
        }
        if digits == 0 {
            return Ok(117);
        }
        if digits != 4 {
            return Ok(0xfffd);
        }
        if let Some(prior) = previous {
            if !(0xdc00..=0xdfff).contains(&value) {
                return Ok(0xfffd);
            }
            value = 0x10000 + ((prior - 0xd800) << 10) + value - 0xdc00;
        }
        Ok(value)
    }
    unsafe fn backslash(&mut self) -> Result<u32, ()> {
        let Some(cp) = self.next() else { return Ok(92) };
        Ok(match cp {
            110 => 10,
            116 => 9,
            114 => 13,
            98 => 8,
            118 => 11,
            102 => 12,
            97 => 7,
            48 => 0,
            117 => {
                let first = self.unicode(None)?;
                if !lead(first) {
                    first
                } else {
                    if self.next() == Some(92) {
                        if self.next() == Some(117) {
                            return self.unicode(Some(first));
                        }
                        self.previous();
                    }
                    self.previous();
                    0xfffd
                }
            }
            _ => cp,
        })
    }
    unsafe fn run(&mut self) -> Result<(), ()> {
        while self.pos < self.len {
            let mut nonempty = false;
            while let Some(mut cp) = self.current() {
                let escaped = cp == 92;
                if escaped {
                    cp = self.backslash()?;
                }
                if !escaped {
                    if space(cp) && self.quote == 0 {
                        self.next();
                        if nonempty {
                            break;
                        }
                        continue;
                    }
                    if cp == 39 || cp == 34 {
                        if self.quote == cp {
                            self.quote = 0;
                            self.next();
                            continue;
                        }
                        if self.quote == 0 {
                            self.quote = cp;
                            self.next();
                            continue;
                        }
                    }
                }
                if (self.emit)(self.ctx, 0, cp) != 0 {
                    return Err(());
                }
                nonempty = true;
                self.next();
            }
            if (self.emit)(self.ctx, 1, 0) != 0 {
                return Err(());
            }
            self.count += 1;
        }
        Ok(())
    }
}
fn span(p: usize, bytes: usize, align: usize) -> Option<(usize, usize)> {
    if p == 0 || p % align != 0 || bytes > isize::MAX as usize {
        return None;
    }
    Some((p, p.checked_add(bytes)?))
}
fn overlaps(a: (usize, usize), b: (usize, usize)) -> bool {
    a.0 < b.1 && b.0 < a.1
}
/// Executes the legacy shell language without retaining any foreign pointer.
///
/// # Safety
/// Input is live initialized u32 storage for len elements; outputs are writable,
/// aligned and disjoint. Callbacks cannot unwind. They may mutate future input,
/// but must keep all allocations live; no Rust references span their execution.
#[no_mangle]
pub unsafe extern "C" fn star_shell_tokenize(
    input: *const u32,
    len: usize,
    classify: Option<StarShellClassify>,
    emit: Option<StarShellEmit>,
    ctx: *mut c_void,
    token_count: *mut usize,
    final_quote: *mut u32,
) -> i32 {
    catch_unwind(AssertUnwindSafe(|| {
        let (Some(classify), Some(emit)) = (classify, emit) else {
            return 2;
        };
        let Some(bytes) = len.checked_mul(4) else {
            return 2;
        };
        if bytes > isize::MAX as usize {
            return 2;
        }
        let Some(count_span) = span(
            token_count as usize,
            std::mem::size_of::<usize>(),
            std::mem::align_of::<usize>(),
        ) else {
            return 2;
        };
        let Some(quote_span) = span(final_quote as usize, 4, 4) else {
            return 2;
        };
        if overlaps(count_span, quote_span) {
            return 2;
        }
        if len != 0 {
            let Some(input_span) = span(input as usize, bytes, 4) else {
                return 2;
            };
            if overlaps(input_span, count_span) || overlaps(input_span, quote_span) {
                return 2;
            }
        }
        let mut parser = Parser {
            input,
            len,
            pos: 0,
            quote: 0,
            count: 0,
            classify,
            emit,
            ctx,
        };
        let status = if parser.run().is_ok() { 0 } else { 1 };
        token_count.write(parser.count);
        final_quote.write(parser.quote);
        CALLS.with(|c| c.set(c.get().wrapping_add(1)));
        status
    }))
    .unwrap_or(3)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct Output {
        current: Vec<u32>,
        words: Vec<Vec<u32>>,
        classes: usize,
        abort: bool,
    }
    unsafe extern "C" fn classify(ctx: *mut c_void, cp: u32, out: *mut u32) -> i32 {
        (*(ctx as *mut Output)).classes += 1;
        out.write(u32::from(matches!(cp, 48..=57 | 65..=70 | 97..=102)));
        0
    }
    unsafe extern "C" fn emit(ctx: *mut c_void, event: u32, cp: u32) -> i32 {
        let o = &mut *(ctx as *mut Output);
        if o.abort {
            return 1;
        }
        if event == 0 {
            o.current.push(cp);
        } else {
            o.words.push(std::mem::take(&mut o.current));
        }
        0
    }
    fn run(s: &str) -> (Output, usize, u32) {
        let input: Vec<u32> = s.chars().map(u32::from).collect();
        let mut output = Output::default();
        let (mut n, mut q) = (999, 999);
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    input.len(),
                    Some(classify),
                    Some(emit),
                    (&mut output as *mut Output).cast(),
                    &mut n,
                    &mut q,
                )
            },
            0
        );
        assert_eq!(n, output.words.len());
        (output, n, q)
    }
    #[test]
    fn literal_legacy_cases() {
        for (s, expected, quote) in [
            ("", vec![], 0),
            ("  ", vec![""], 0),
            ("a ", vec!["a"], 0),
            ("a  ", vec!["a", ""], 0),
            ("a''b\"c", vec!["abc"], 34),
            ("\\u", vec!["u"], 0),
            ("\\u12", vec!["�"], 0),
            ("\\u0041Z", vec!["AZ"], 0),
            ("\\uD83D\\uDE00", vec!["😀"], 0),
            ("\\uD800X", vec!["�X"], 0),
            ("\\uD800\\x", vec!["�x"], 0),
            ("\\u12 z", vec!["�z"], 0),
            ("a\0b", vec!["a\0b"], 0),
            ("\\", vec!["\\"], 0),
        ] {
            let (output, _, q) = run(s);
            assert_eq!(
                output.words,
                expected
                    .iter()
                    .map(|s| s.chars().map(u32::from).collect::<Vec<_>>())
                    .collect::<Vec<_>>(),
                "{s:?}"
            );
            assert_eq!(q, quote);
        }
        assert_eq!(run("é😀").0.classes, 0);
    }
    unsafe extern "C" fn noop_classify(_: *mut c_void, _: u32, out: *mut u32) -> i32 {
        out.write(0);
        0
    }
    unsafe extern "C" fn noop_emit(_: *mut c_void, _: u32, _: u32) -> i32 {
        0
    }

    #[test]
    fn empty_null_and_invalid_spans() {
        let (mut n, mut q) = (99usize, 99u32);
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    std::ptr::null(),
                    0,
                    Some(noop_classify),
                    Some(noop_emit),
                    std::ptr::null_mut(),
                    &mut n,
                    &mut q,
                )
            },
            0
        );
        assert_eq!((n, q), (0, 0));
        let input = [97u32; 4];
        let before = star_shell_call_count();
        for (p, len) in [
            (std::ptr::null(), 1),
            (1usize as *const u32, 1),
            ((usize::MAX - 3) as *const u32, 2),
            (input.as_ptr(), isize::MAX as usize / 4 + 1),
            (input.as_ptr(), usize::MAX),
        ] {
            n = 99;
            q = 99;
            assert_eq!(
                unsafe {
                    star_shell_tokenize(
                        p,
                        len,
                        Some(noop_classify),
                        Some(noop_emit),
                        std::ptr::null_mut(),
                        &mut n,
                        &mut q,
                    )
                },
                2
            );
            assert_eq!((n, q), (99, 99));
        }
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    (&n as *const usize).cast(),
                    1,
                    Some(noop_classify),
                    Some(noop_emit),
                    std::ptr::null_mut(),
                    &mut n,
                    &mut q,
                )
            },
            2
        );
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    1,
                    Some(noop_classify),
                    Some(noop_emit),
                    std::ptr::null_mut(),
                    &mut n,
                    (&mut n as *mut usize).cast(),
                )
            },
            2
        );
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    1,
                    Some(noop_classify),
                    Some(noop_emit),
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                    &mut q,
                )
            },
            2
        );
        assert_eq!(star_shell_call_count(), before);
    }

    struct Mutation {
        input: *mut u32,
        output: Output,
        nested: bool,
    }
    unsafe extern "C" fn mutating_emit(ctx: *mut c_void, event: u32, cp: u32) -> i32 {
        let m = ctx as *mut Mutation;
        if event == 0 && !(*m).nested {
            (*m).nested = true;
            (*m).input.add(1).write(122);
            let (mut n, mut q) = (99, 99);
            assert_eq!(
                star_shell_tokenize(
                    std::ptr::null(),
                    0,
                    Some(noop_classify),
                    Some(noop_emit),
                    std::ptr::null_mut(),
                    &mut n,
                    &mut q
                ),
                0
            );
        }
        emit(std::ptr::addr_of_mut!((*m).output).cast(), event, cp)
    }
    #[test]
    fn callback_mutation_reentrancy_and_partial_count() {
        let mut input = [97, 98];
        let mut m = Mutation {
            input: input.as_mut_ptr(),
            output: Output::default(),
            nested: false,
        };
        let (mut n, mut q) = (99, 99);
        let before = star_shell_call_count();
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    2,
                    Some(noop_classify),
                    Some(mutating_emit),
                    (&mut m as *mut Mutation).cast(),
                    &mut n,
                    &mut q,
                )
            },
            0
        );
        assert_eq!(m.output.words, vec![vec![97, 122]]);
        assert_eq!((n, q), (1, 0));
        assert_eq!(star_shell_call_count(), before + 2);
        unsafe extern "C" fn abort_second_word(ctx: *mut c_void, event: u32, cp: u32) -> i32 {
            if event == 1 && (*(ctx as *mut Output)).words.len() == 1 {
                return 1;
            }
            emit(ctx, event, cp)
        }
        let mut output = Output::default();
        let input = [97, 32, 39, 98];
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    input.len(),
                    Some(noop_classify),
                    Some(abort_second_word),
                    (&mut output as *mut Output).cast(),
                    &mut n,
                    &mut q,
                )
            },
            1
        );
        assert_eq!((n, q), (1, 39));
        assert_eq!(output.words, vec![vec![97]]);
        assert_eq!(output.current, vec![98]);
    }

    #[test]
    fn receipts_are_thread_local() {
        let before = star_shell_call_count();
        std::thread::spawn(|| {
            assert_eq!(star_shell_call_count(), 0);
            run("a");
            assert_eq!(star_shell_call_count(), 1);
        })
        .join()
        .unwrap();
        assert_eq!(star_shell_call_count(), before);
    }

    #[test]
    fn invalid_and_abort_receipts() {
        let (mut n, mut q) = (99, 99);
        let before = star_shell_call_count();
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    std::ptr::null(),
                    0,
                    None,
                    Some(emit),
                    std::ptr::null_mut(),
                    &mut n,
                    &mut q,
                )
            },
            2
        );
        assert_eq!((n, q), (99, 99));
        assert_eq!(star_shell_call_count(), before);
        let mut output = Output {
            abort: true,
            ..Output::default()
        };
        let input = [97];
        assert_eq!(
            unsafe {
                star_shell_tokenize(
                    input.as_ptr(),
                    1,
                    Some(classify),
                    Some(emit),
                    (&mut output as *mut Output).cast(),
                    &mut n,
                    &mut q,
                )
            },
            1
        );
        assert_eq!((n, q), (0, 0));
        assert_eq!(star_shell_call_count(), before + 1);
    }
}
