use std::cell::Cell;
use std::panic::{catch_unwind, AssertUnwindSafe};

thread_local! {
    static CALLS: Cell<[u64; 5]> = const { Cell::new([0; 5]) };
}

#[no_mangle]
pub extern "C" fn star_encode_call_count(operation: u32) -> u64 {
    CALLS.with(|c| c.get().get(operation as usize).copied().unwrap_or(0))
}

fn range(p: usize, n: usize) -> Option<(usize, usize)> {
    if n > isize::MAX as usize || (n != 0 && p == 0) {
        return None;
    }
    Some((p, p.checked_add(n)?))
}
fn overlaps(a: (usize, usize), b: (usize, usize)) -> bool {
    a.0 != a.1 && b.0 != b.1 && a.0 < b.1 && b.0 < a.1
}
fn nibble(c: u8) -> u8 {
    match c {
        b'0'..=b'9' => c - b'0',
        b'A'..=b'F' => c - b'A' + 10,
        b'a'..=b'f' => c - b'a' + 10,
        _ => 0,
    }
}
fn sextet(c: u8) -> u8 {
    match c {
        b'A'..=b'Z' => c - b'A',
        b'a'..=b'z' => c - b'a' + 26,
        b'0'..=b'9' => c - b'0' + 52,
        b'+' | b'-' => 62,
        b'/' | b'_' => 63,
        _ => 255, // locale-accepted bytes retain std::string::npos narrowing.
    }
}
fn contain(f: impl FnOnce() -> i32) -> i32 {
    catch_unwind(AssertUnwindSafe(f)).unwrap_or(3)
}

/// # Safety
/// Nonempty ranges must be live allocations, readable for input/table and writable
/// for output/written. Integer range checks cannot prove allocation provenance.
/// Empty ranges may be null. No pointers are retained. A panic can leave partial
/// output, so callers must not retry through another implementation on status 3.
#[no_mangle]
pub unsafe extern "C" fn star_encode(
    operation: u32,
    input: *const u8,
    input_len: usize,
    output: *mut u8,
    output_capacity: usize,
    use_url: u32,
    accepted256: *const u8,
    written: *mut usize,
) -> i32 {
    contain(|| {
        if operation > 4
            || (operation == 3 && use_url > 1)
            || written.is_null()
            || (written as usize) % std::mem::align_of::<usize>() != 0
        {
            return 2;
        }
        let Some(ir) = range(input as usize, input_len) else {
            return 2;
        };
        let Some(or) = range(output as usize, output_capacity) else {
            return 2;
        };
        let Some(wr) = range(written as usize, std::mem::size_of::<usize>()) else {
            return 2;
        };
        let tr = if operation == 4 {
            let Some(r) = range(accepted256 as usize, 256) else {
                return 2;
            };
            r
        } else {
            (0, 0)
        };
        if overlaps(ir, or)
            || overlaps(or, tr)
            || overlaps(wr, ir)
            || overlaps(wr, or)
            || overlaps(wr, tr)
        {
            return 2;
        }
        let n = execute(
            operation,
            input,
            input_len,
            output,
            output_capacity,
            use_url,
            accepted256,
        );
        written.write(n);
        CALLS.with(|c| {
            let mut counts = c.get();
            counts[operation as usize] = counts[operation as usize].wrapping_add(1);
            c.set(counts);
        });
        0
    })
}

// Raw accesses deliberately avoid creating references to foreign allocations.
unsafe fn execute(
    op: u32,
    input: *const u8,
    len: usize,
    out: *mut u8,
    cap: usize,
    url: u32,
    table: *const u8,
) -> usize {
    let mut written = 0;
    if cap == 0 {
        return 0;
    }
    match op {
        0 => {
            let count = len.min(cap / 2);
            let hex = b"0123456789abcdef";
            for i in 0..count {
                let b = input.add(i).read();
                out.add(2 * i).write(hex[(b >> 4) as usize]);
                out.add(2 * i + 1).write(hex[(b & 15) as usize]);
            }
            count * 2
        }
        1 => {
            let count = cap.min(len / 2);
            for i in 0..count {
                out.add(i).write(
                    (nibble(input.add(2 * i).read()) << 4) | nibble(input.add(2 * i + 1).read()),
                );
            }
            count
        }
        2 => {
            let count = cap.min(len);
            for i in 0..count {
                out.add(i).write(nibble(input.add(i).read()));
            }
            count
        }
        3 => {
            let alphabet = if url == 1 {
                b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            } else {
                b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
            };
            let mut pos = 0;
            while pos < len {
                let take = (len - pos).min(3);
                let a = input.add(pos).read();
                let b = if take > 1 {
                    input.add(pos + 1).read()
                } else {
                    0
                };
                let c = if take > 2 {
                    input.add(pos + 2).read()
                } else {
                    0
                };
                let group = [
                    alphabet[(a >> 2) as usize],
                    alphabet[(((a & 3) << 4) | (b >> 4)) as usize],
                    if take > 1 {
                        alphabet[(((b & 15) << 2) | (c >> 6)) as usize]
                    } else {
                        b'='
                    },
                    if take > 2 {
                        alphabet[(c & 63) as usize]
                    } else {
                        b'='
                    },
                ];
                let count = if url == 1 { take + 1 } else { 4 };
                for &byte in &group[..count] {
                    out.add(written).write(byte);
                    written += 1;
                    if written == cap {
                        return written;
                    }
                }
                pos += take;
            }
            written
        }
        4 => {
            let mut pos = 0;
            loop {
                let mut group = [255u8; 4];
                let mut count = 0;
                while count < 4 && pos < len {
                    let c = input.add(pos).read();
                    if c == b'=' || table.add(c as usize).read() == 0 {
                        break;
                    }
                    group[count] = sextet(c);
                    count += 1;
                    pos += 1;
                }
                // C++ promotes then narrows each result to U8, including 255.
                let bytes = [
                    group[0]
                        .wrapping_shl(2)
                        .wrapping_add((group[1] & 0x30) >> 4),
                    (group[1] & 15)
                        .wrapping_shl(4)
                        .wrapping_add((group[2] & 0x3c) >> 2),
                    (group[2] & 3).wrapping_shl(6).wrapping_add(group[3]),
                ];
                for &byte in &bytes[..count.saturating_sub(1)] {
                    out.add(written).write(byte);
                    written += 1;
                    if written == cap {
                        return written;
                    }
                }
                if count < 4 {
                    return written;
                }
            }
        }
        _ => unreachable!(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn table() -> [u8; 256] {
        std::array::from_fn(|i| {
            u8::from((i as u8).is_ascii_alphanumeric() || b"+/-_".contains(&(i as u8)))
        })
    }
    fn run(op: u32, input: &[u8], cap: usize, url: u32) -> Vec<u8> {
        let mut output = vec![0xa5; cap + 2];
        let mut n = usize::MAX;
        assert_eq!(
            unsafe {
                star_encode(
                    op,
                    input.as_ptr(),
                    input.len(),
                    output.as_mut_ptr().add(1),
                    cap,
                    url,
                    table().as_ptr(),
                    &mut n,
                )
            },
            0
        );
        assert_eq!(output[0], 0xa5);
        assert!(n <= cap);
        assert!(output[n + 1..].iter().all(|b| *b == 0xa5));
        output[1..n + 1].to_vec()
    }
    #[test]
    fn exhaustive_hex() {
        for a in 0..=255u8 {
            assert_eq!(run(2, &[a], 1, 0), [nibble(a)]);
            let encoded = run(0, &[a], 2, 0);
            assert_eq!(run(1, &encoded, 1, 0), [a]);
            assert!(run(0, &[a], 1, 0).is_empty());
            for b in 0..=255u8 {
                assert_eq!(run(1, &[a, b, 99], 2, 0), [(nibble(a) << 4) | nibble(b)]);
            }
        }
    }
    #[test]
    fn groups_padding_capacity() {
        for (plain, encoded) in [
            ("", ""),
            ("f", "Zg=="),
            ("fo", "Zm8="),
            ("foo", "Zm9v"),
            ("foob", "Zm9vYg=="),
            ("foobar", "Zm9vYmFy"),
        ] {
            for url in 0..=1 {
                let text = if url == 1 {
                    encoded.trim_end_matches('=')
                } else {
                    encoded
                };
                for cap in 0..=encoded.len() + 2 {
                    assert_eq!(
                        run(3, plain.as_bytes(), cap, url),
                        &text.as_bytes()[..cap.min(text.len())]
                    );
                    assert_eq!(
                        run(4, text.as_bytes(), cap, 9),
                        &plain.as_bytes()[..cap.min(plain.len())]
                    );
                }
            }
        }
        for text in [b"Zg extra".as_slice(), b"Zg\0v", b"Zg=v", b"Zh=="] {
            assert_eq!(run(4, text, 20, 0), b"f");
        }
        assert_eq!(run(4, b"Z", 20, 0), b"");
        assert_eq!(run(4, b"-_+_", 20, 0), [251, 255, 191]);
        let mut t = table();
        t[128] = 1;
        let mut out = [0; 3];
        let mut n = 0;
        assert_eq!(
            unsafe {
                star_encode(
                    4,
                    [128; 4].as_ptr(),
                    4,
                    out.as_mut_ptr(),
                    3,
                    0,
                    t.as_ptr(),
                    &mut n,
                )
            },
            0
        );
        assert_eq!(out, [255, 255, 191]);
    }
    #[test]
    fn bytes_group_boundaries_and_threads() {
        let alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        for byte in 0..=255u8 {
            assert_eq!(
                run(3, &[byte], 4, 0),
                [
                    alphabet[(byte >> 2) as usize],
                    alphabet[((byte & 3) << 4) as usize],
                    b'=',
                    b'='
                ]
            );
        }
        for len in 0..=33 {
            let bytes: Vec<u8> = (0..len).map(|i| (i * 73 + 189) as u8).collect();
            for url in 0..=1 {
                let full = run(3, &bytes, 100, url);
                assert_eq!(run(4, &full, 100, 0), bytes);
                for cap in 0..=full.len() + 1 {
                    assert_eq!(run(3, &bytes, cap, url), full[..cap.min(full.len())]);
                    assert_eq!(run(4, &full, cap, 0), bytes[..cap.min(bytes.len())]);
                }
            }
        }
        let workers: Vec<_> = (0..4)
            .map(|_| {
                std::thread::spawn(|| {
                    for op in 0..5 {
                        assert_eq!(star_encode_call_count(op), 0);
                        run(op, b"abcd", 8, 0);
                        for other in 0..5 {
                            assert_eq!(star_encode_call_count(other), u64::from(other <= op));
                        }
                    }
                })
            })
            .collect();
        for worker in workers {
            worker.join().unwrap();
        }
    }

    #[test]
    fn alias_and_null_validation() {
        let mut storage = [0usize; 40];
        let p = storage.as_mut_ptr().cast::<u8>();
        let mut n = 777;
        let null = std::ptr::null();
        let sentinel = &n as *const usize;
        let check = |input, len, output, cap, table, written| {
            assert_eq!(
                unsafe { star_encode(4, input, len, output, cap, 0, table, written) },
                2
            );
            assert_eq!(unsafe { sentinel.read() }, 777);
            assert_eq!(storage, [0; 40]);
        };
        check(null, 0, std::ptr::null_mut(), 1, table().as_ptr(), &mut n);
        check(p, 8, unsafe { p.add(4) }, 8, table().as_ptr(), &mut n);
        check(null, 0, p, 8, p, &mut n);
        check(p, 8, std::ptr::null_mut(), 0, table().as_ptr(), p.cast());
        check(null, 0, std::ptr::null_mut(), 0, p, p.cast());
        check(
            null,
            0,
            std::ptr::null_mut(),
            0,
            table().as_ptr(),
            std::ptr::null_mut(),
        );
    }

    #[test]
    fn validation_and_receipts() {
        let mut buf = [0xa5u8; 32];
        let mut n = 777;
        let p = buf.as_mut_ptr();
        let null = std::ptr::null();
        for (op, input, len, output, cap, url, t, w) in [
            (5, null, 0, p, 1, 0, null, &mut n as *mut usize),
            (3, null, 0, p, 1, 2, null, &mut n),
            (0, null, 1, p, 1, 0, null, &mut n),
            (0, p as *const u8, 2, p, 2, 0, null, &mut n),
            (4, null, 0, p, 1, 0, null, &mut n),
            (0, null, 0, p, 8, 0, null, p as *mut usize),
            (0, null, 0, p, 0, 0, null, unsafe { p.add(1) } as *mut usize),
            (0, usize::MAX as *const u8, 2, p, 1, 0, null, &mut n),
        ] {
            assert_eq!(
                unsafe { star_encode(op, input, len, output, cap, url, t, w) },
                2
            );
            assert_eq!(n, 777);
            assert_eq!(buf, [0xa5; 32]);
        }
        let before = star_encode_call_count(0);
        assert_eq!(
            unsafe { star_encode(0, null, 0, std::ptr::null_mut(), 0, 0, null, &mut n) },
            0
        );
        assert_eq!(n, 0);
        assert_eq!(star_encode_call_count(0), before + 1);
        assert_eq!(star_encode_call_count(99), 0);
        std::thread::spawn(|| {
            for op in 0..5 {
                assert_eq!(star_encode_call_count(op), 0);
            }
        })
        .join()
        .unwrap();
        assert_eq!(contain(|| panic!("contained test")), 3);
        assert_eq!(star_encode_call_count(0), before + 1);
    }
}
