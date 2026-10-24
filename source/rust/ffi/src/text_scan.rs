use std::cell::Cell;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

pub type StarTextScanHost = unsafe extern "C" fn(*mut c_void, u32, u64, u64) -> u32;
thread_local! { static CALLS: Cell<[u64; 3]> = const { Cell::new([0; 3]) }; }
fn count(index: usize) {
    CALLS.with(|c| {
        let mut counts = c.get();
        counts[index] = counts[index].wrapping_add(1);
        c.set(counts);
    });
}
#[no_mangle]
pub extern "C" fn star_text_scan_call_count(index: u32) -> u64 {
    CALLS.with(|c| c.get().get(index as usize).copied().unwrap_or(0))
}
fn escape(byte: u8) -> bool {
    byte == b'^' || byte == 27
}
unsafe fn emit(
    host: StarTextScanHost,
    ctx: *mut c_void,
    kind: u32,
    offset: usize,
    length: usize,
) -> Result<bool, u32> {
    count(kind as usize + 1);
    match host(ctx, kind, offset as u64, length as u64) {
        0 => Ok(true),
        1 => Ok(false),
        2 => Err(1),
        _ => Err(2),
    }
}
// Only raw byte loads: a callback can edit future bytes or reenter. In
// particular, do not hold a Rust input slice across a host invocation.
unsafe fn scan(
    data: *const u8,
    length: usize,
    commands: bool,
    sides: bool,
    host: StarTextScanHost,
    ctx: *mut c_void,
) -> Result<bool, u32> {
    let mut base = 0;
    let mut start = 0;
    loop {
        let mut pos = base + start;
        while pos < length && !escape(data.add(pos).read()) {
            pos += 1;
        }
        start = 0;
        if pos < length {
            while pos < length && escape(data.add(pos).read()) {
                pos += 1;
            }
            // The legacy npos - 1 path for an all-escape suffix finds no end.
            if pos < length {
                let esc = pos - 1;
                let mut end = pos;
                while end < length {
                    let byte = data.add(end).read();
                    if escape(byte) || byte == b';' {
                        break;
                    }
                    end += 1;
                }
                if end < length {
                    if data.add(end).read() != b';' {
                        start = end - base;
                        continue;
                    }
                    // Freeze boundaries before text callback; observe current
                    // bytes when dispatching commands, then scan the remainder.
                    if esc > base && !emit(host, ctx, 0, base, esc - base)? {
                        return Ok(false);
                    }
                    if commands {
                        let offset = if sides { esc } else { esc + 1 };
                        let size = if sides { end - esc + 1 } else { end - esc - 1 };
                        if size != 0 && !emit(host, ctx, 1, offset, size)? {
                            return Ok(false);
                        }
                    }
                    base = end + 1;
                    continue;
                }
            }
        }
        return if base < length {
            emit(host, ctx, 0, base, length - base)
        } else {
            Ok(true)
        };
    }
}

/// # Safety
/// Input is initialized/live through return; callbacks may mutate without
/// reallocating. Output is live/exclusively writable for one byte, and may
/// overlap input. Host never unwinds through this ABI and obeys the header.
#[no_mangle]
pub unsafe extern "C" fn star_text_scan_process(
    data: *const u8,
    length: u64,
    has_commands: u8,
    include_sides: u8,
    host: Option<StarTextScanHost>,
    context: *mut c_void,
    out_bool: *mut u8,
) -> u32 {
    let Ok(length) = usize::try_from(length) else {
        return 2;
    };
    if has_commands > 1
        || include_sides > 1
        || host.is_none()
        || out_bool.is_null()
        || (out_bool as usize).checked_add(1).is_none()
        || (length != 0
            && (data.is_null()
                || length > isize::MAX as usize
                || (data as usize).checked_add(length).is_none()))
    {
        return 2;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        count(0);
        scan(
            data,
            length,
            has_commands != 0,
            include_sides != 0,
            host.unwrap(),
            context,
        )
    })) {
        Ok(Ok(value)) => {
            out_bool.write(value as u8);
            0
        }
        Ok(Err(status)) => status,
        Err(_) => 3,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[derive(Default)]
    struct State {
        data: *mut u8,
        events: Vec<(u32, Vec<u8>)>,
        action: u32,
    }
    unsafe extern "C" fn host(ctx: *mut c_void, kind: u32, offset: u64, size: u64) -> u32 {
        let s = &mut *(ctx as *mut State);
        s.events.push((
            kind,
            std::slice::from_raw_parts(s.data.add(offset as usize), size as usize).to_vec(),
        ));
        if s.action == 4 && s.events.len() == 1 {
            s.data.add(2).write(b'Z');
        }
        if s.action == 6 && s.events.len() == 1 {
            s.data.add(3).write(b'^'); // old terminator must remain the boundary
            s.data.add(5).write(b'Q'); // later scanning sees changed bytes
        }
        if s.action == 7 && kind == 1 && s.events.len() == 2 {
            s.data.add(4).write(b'^');
            s.data.add(5).write(b'z');
            s.data.add(6).write(b';');
        }
        if s.action == 5 && s.events.len() == 1 {
            let mut out = 9;
            assert_eq!(
                star_text_scan_process(
                    std::ptr::null(),
                    0,
                    0,
                    0,
                    Some(host),
                    std::ptr::null_mut(),
                    &mut out
                ),
                0
            );
            assert_eq!(out, 1);
        }
        if s.action <= 3 {
            s.action
        } else {
            0
        }
    }
    unsafe fn run(bytes: &mut [u8], sides: u8, action: u32) -> (u32, u8, State) {
        let mut s = State {
            data: bytes.as_mut_ptr(),
            events: vec![],
            action,
        };
        let mut out = 9;
        let status = star_text_scan_process(
            s.data,
            bytes.len() as u64,
            1,
            sides,
            Some(host),
            &mut s as *mut _ as *mut c_void,
            &mut out,
        );
        (status, out, s)
    }
    #[test]
    fn anchors_and_all_bytes() {
        unsafe {
            let (_, out, s) = run(&mut b"A^^red;B^reset;C".to_vec(), 0, 0);
            assert_eq!(out, 1);
            assert_eq!(
                s.events,
                vec![
                    (0, b"A^".to_vec()),
                    (1, b"red".to_vec()),
                    (0, b"B".to_vec()),
                    (1, b"reset".to_vec()),
                    (0, b"C".to_vec())
                ]
            );
            assert_eq!(
                run(&mut b"^a^b;".to_vec(), 0, 0).2.events,
                vec![(0, b"^a".to_vec()), (1, b"b".to_vec())]
            );
            assert!(run(&mut b"^;".to_vec(), 0, 0).2.events.is_empty());
            assert_eq!(
                run(&mut b"^;".to_vec(), 1, 0).2.events,
                vec![(1, b"^;".to_vec())]
            );
            assert_eq!(
                run(&mut b"^^".to_vec(), 0, 0).2.events,
                vec![(0, b"^^".to_vec())]
            );
            for byte in 0..=255u8 {
                let mut bytes = [byte];
                assert_eq!(run(&mut bytes, 0, 0).2.events, vec![(0, vec![byte])]);
            }
        }
    }
    #[test]
    fn mutation_reentry_and_status() {
        unsafe {
            assert_eq!(
                run(&mut b"A^x;B".to_vec(), 0, 4).2.events[1],
                (1, b"Z".to_vec())
            );
            let before = star_text_scan_call_count(0);
            assert_eq!(run(&mut b"A^x;B".to_vec(), 0, 5).0, 0);
            assert_eq!(star_text_scan_call_count(0), before + 2);
            for (action, status, out) in [(1, 0, 0), (2, 1, 9), (3, 2, 9)] {
                let result = run(&mut b"A^x;B".to_vec(), 0, action);
                assert_eq!(
                    (result.0, result.1, result.2.events.len()),
                    (status, out, 1)
                );
            }
        }
    }
    #[test]
    fn frozen_boundaries_and_lazy_remainder() {
        unsafe {
            assert_eq!(
                run(&mut b"A^x;^y;Z".to_vec(), 0, 6).2.events,
                vec![
                    (0, b"A".to_vec()),
                    (1, b"x".to_vec()),
                    (1, b"Q".to_vec()),
                    (0, b"Z".to_vec())
                ]
            );
            assert_eq!(
                run(&mut b"A^x;abc".to_vec(), 0, 7).2.events,
                vec![(0, b"A".to_vec()), (1, b"x".to_vec()), (1, b"z".to_vec())]
            );
        }
    }
    #[test]
    fn attempt_counters_and_absent_commands() {
        unsafe {
            let before = [
                star_text_scan_call_count(0),
                star_text_scan_call_count(1),
                star_text_scan_call_count(2),
            ];
            assert_eq!(run(&mut b"^x;after".to_vec(), 0, 1).1, 0);
            assert_eq!(
                [
                    star_text_scan_call_count(0),
                    star_text_scan_call_count(1),
                    star_text_scan_call_count(2)
                ],
                [before[0] + 1, before[1], before[2] + 1]
            );
            let mut bytes = *b"^red;TEXT^reset;";
            let mut s = State {
                data: bytes.as_mut_ptr(),
                events: vec![],
                action: 0,
            };
            let mut out = 9;
            assert_eq!(
                star_text_scan_process(
                    s.data,
                    bytes.len() as u64,
                    0,
                    0,
                    Some(host),
                    &mut s as *mut _ as *mut c_void,
                    &mut out
                ),
                0
            );
            assert_eq!(s.events, vec![(0, b"TEXT".to_vec())]);
            assert_eq!(out, 1);
            assert_eq!(star_text_scan_call_count(3), 0);
        }
    }
    #[test]
    fn metadata_alias_and_empty() {
        unsafe {
            let before = star_text_scan_call_count(0);
            let mut out = 9;
            for (data, len, flag, callback, output) in [
                (
                    std::ptr::null(),
                    1,
                    0,
                    Some(host as StarTextScanHost),
                    &mut out as *mut u8,
                ),
                (
                    std::ptr::null(),
                    0,
                    2,
                    Some(host as StarTextScanHost),
                    &mut out,
                ),
                (std::ptr::null(), 0, 0, None, &mut out),
                (
                    usize::MAX as *const u8,
                    1,
                    0,
                    Some(host as StarTextScanHost),
                    &mut out,
                ),
                (
                    std::ptr::null(),
                    0,
                    0,
                    Some(host as StarTextScanHost),
                    std::ptr::null_mut(),
                ),
            ] {
                assert_eq!(
                    star_text_scan_process(
                        data,
                        len,
                        flag,
                        0,
                        callback,
                        std::ptr::null_mut(),
                        output
                    ),
                    2
                );
            }
            assert_eq!(out, 9);
            assert_eq!(star_text_scan_call_count(0), before);
            assert_eq!(
                star_text_scan_process(
                    usize::MAX as *const u8,
                    0,
                    0,
                    0,
                    Some(host),
                    std::ptr::null_mut(),
                    &mut out
                ),
                0
            );
            assert_eq!(out, 1);
            let mut bytes = *b"abc";
            let mut s = State {
                data: bytes.as_mut_ptr(),
                events: vec![],
                action: 0,
            };
            assert_eq!(
                star_text_scan_process(
                    s.data,
                    3,
                    0,
                    0,
                    Some(host),
                    &mut s as *mut _ as *mut c_void,
                    s.data
                ),
                0
            );
            assert_eq!(s.events, vec![(0, b"abc".to_vec())]);
            assert_eq!(bytes, [1, b'b', b'c']);
        }
    }
}
