use super::*;

fn params() -> StarLightingParameters {
    StarLightingParameters {
        spread_passes: 1,
        spread_max_air: 4.0,
        spread_max_obstacle: 2.0,
        point_max_air: 4.0,
        point_max_obstacle: 2.0,
        point_obstacle_boost: 0.0,
        point_additive: 0,
    }
}
fn point() -> StarLightingPointLight {
    StarLightingPointLight {
        position: [2.5, 2.5],
        value: [1.0, 0.5, 0.25],
        beam: 0.0,
        beam_angle: 0.0,
        beam_ambience: 0.0,
        as_spread: 0,
    }
}
fn array(cells: &mut [StarLightingCell], n: usize) -> Array<'_> {
    Array {
        width: 5,
        height: 5,
        n,
        p: params(),
        cells,
    }
}
#[test]
fn arm_fast_is_explicit_and_independent_of_precise_calls() {
    // The fixed bits come from the isolated clang 21 ARM probe, not a tolerance.
    // One interior source in a 3x3 grid makes its right neighbour a single spread.
    let run = |calculate: Calculate, expected| {
        let mut cells = [StarLightingCell::default(); 9];
        cells[4].light = [
            0.24970240890979767,
            0.05007189139723778,
            0.04367992654442787,
        ];
        let mut p = params();
        p.spread_max_air = 5.0;
        let before = star_lighting_call_count();
        assert_eq!(
            unsafe {
                calculate(
                    3,
                    3,
                    3,
                    &p,
                    cells.as_mut_ptr(),
                    9,
                    std::ptr::null(),
                    0,
                    std::ptr::null(),
                    0,
                    0,
                    0,
                    3,
                    3,
                )
            },
            0
        );
        assert_eq!(cells[7].light[0].to_bits(), expected);
        assert!(star_lighting_call_count() > before);
    };
    std::thread::scope(|scope| {
        scope.spawn(|| {
            for _ in 0..32 {
                run(star_lighting_calculate, 0x3d4b94c0);
            }
        });
        scope.spawn(|| {
            for _ in 0..32 {
                run(star_lighting_calculate_arm_fast, 0x3d4b94bf);
            }
        });
    });
}

#[test]
fn arm_fast_sampled_rgb_expressions_retain_probed_rounding() {
    let source = [2.6911070346832275, 2.811753511428833, 2.6305959224700928];
    let dest = [
        0.03542102873325348,
        0.028175126761198044,
        0.08660677075386047,
    ];
    assert_eq!(
        spread::<false>(source, dest, 0.6016060709953308, 3)[0],
        2.115314483642578
    );
    assert_eq!(
        spread::<true>(source, dest, 0.6016060709953308, 3)[0],
        2.1153147220611572
    );
    let source = [1.0632493495941162, 1.8769252300262451, 2.188105583190918];
    assert_eq!(
        subtract::<false>(source, 0.4833781123161316, 3)[0],
        0.8283651471138
    );
    assert_eq!(
        subtract::<true>(source, 0.4833781123161316, 3)[0],
        0.8283650875091553
    );
}

#[test]
fn abi_layout() {
    assert_eq!(size_of::<StarLightingParameters>(), 28);
    assert_eq!(size_of::<StarLightingCell>(), 16);
    assert_eq!(size_of::<StarLightingSpreadLight>(), 20);
    assert_eq!(size_of::<StarLightingPointLight>(), 36);
    assert_eq!(align_of::<StarLightingPointLight>(), 4);
}
#[test]
fn proportional_color_and_scalar_subtraction_differ() {
    assert_eq!(
        subtract::<false>([1.0, 0.5, 0.25], 0.5, 3),
        [0.5, 0.25, 0.125]
    );
    assert_eq!(
        subtract::<false>([1.0, 0.5, 0.25], 0.5, 1),
        [0.5, 0.5, 0.25]
    );
    assert_eq!(
        spread::<false>([1.0, 0.5, 0.25], [0.0; 3], 0.5, 3),
        [0.5, 0.25, 0.125]
    );
    assert_eq!(subtract::<false>([-1.0; 3], 0.5, 3), [-1.0; 3]);
}
#[test]
fn placement_is_column_major_and_obstacle_dependent() {
    let mut cells = [StarLightingCell::default(); 25];
    let mut a = array(&mut cells, 3);
    a.sources(&[StarLightingSpreadLight {
        position: [1.0, 2.0],
        value: [1.0, 0.5, 0.25],
    }]);
    for i in [1, 2, 6, 7] {
        assert_eq!(a.cells[i].light, [0.75, 0.375, 0.1875]);
    }
    assert_eq!(a.cells[10].light, [0.0; 3]);
    a.cells.fill(StarLightingCell::default());
    a.cells[7].obstacle = 1;
    a.sources(&[StarLightingSpreadLight {
        position: [1.0, 2.0],
        value: [1.0, 0.5, 0.25],
    }]);
    assert_eq!(a.cells[1].light, [0.5, 0.25, 0.125]);
}
#[test]
fn sweeps_keep_legacy_border_behavior_and_source_dropoff() {
    let mut cells = [StarLightingCell::default(); 25];
    let mut a = array(&mut cells, 1);
    a.cells[12].light[0] = 1.0;
    a.sweeps([0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.75);
    assert_eq!(a.cells[7].light[0], 0.75);
    assert_eq!(a.cells[13].light[0], 0.75);
    assert_eq!(a.cells[11].light[0], 0.75);
    let diag = (0.25_f64 * std::f64::consts::SQRT_2) as f32;
    assert_eq!(a.cells[18].light[0], 1.0 - diag);
    assert_eq!(a.cells[24].light[0], (1.0 - diag) - diag); // border cells receive light but never become sweep sources
    a.cells.fill(StarLightingCell::default());
    a.cells[12] = StarLightingCell {
        light: [1.0, 0.0, 0.0],
        obstacle: 1,
    };
    a.sweeps([0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.5);
}
#[test]
fn wu_axis_transpose_endpoint_weights_and_cap() {
    let mut cells = [StarLightingCell::default(); 25];
    let a = array(&mut cells, 1);
    a.cells[12].obstacle = 1;
    assert_eq!(a.line([1.5, 2.5], [3.5, 2.5], 0.25, 1.0), 0.25);
    assert_eq!(a.line([2.5, 1.5], [2.5, 3.5], 0.25, 1.0), 0.25);
    assert_eq!(a.line([3.5, 2.5], [1.5, 2.5], 0.25, 1.0), 0.25);
    assert_eq!(a.line([1.5, 2.5], [3.5, 2.5], 0.25, 0.1), 0.1);
    a.cells[7].obstacle = 1;
    assert_eq!(a.line([1.5, 2.5], [3.5, 2.5], 0.25, 1.0), 0.375);
}
#[test]
fn point_modes_hybrid_and_zero_distance_quirk() {
    let mut cells = [StarLightingCell::default(); 25];
    let mut a = array(&mut cells, 3);
    a.cells[12].light = [0.25; 3];
    a.points(&[point()], [0, 0, 5, 5]);
    assert_eq!(a.cells[12].light, [1.25, 0.75, 0.5]);
    assert_eq!(a.cells[17].light, [0.75, 0.375, 0.1875]);
    a.cells.fill(StarLightingCell::default());
    a.p.point_additive = 1;
    let mut p = point();
    p.as_spread = 1;
    a.points(&[p], [0, 0, 5, 5]);
    assert_eq!(
        a.cells[17].light,
        [0.75 * 0.15, 0.375 * 0.15, 0.1875 * 0.15]
    );
    assert_eq!(a.cells[12].light, p.value);
}
#[test]
fn tiny_beam_has_distinct_scalar_and_rgb_thresholds() {
    let mut scalar = [StarLightingCell::default(); 25];
    let mut rgb = scalar;
    let mut p = point();
    p.beam = 0.00005;
    array(&mut scalar, 1).points(&[p], [0, 0, 5, 5]);
    array(&mut rgb, 3).points(&[p], [0, 0, 5, 5]);
    assert_eq!(scalar[7].light[0], 0.75);
    assert!(rgb[7].light[0] < scalar[7].light[0]);
    assert_eq!(rgb[17].light[0], scalar[17].light[0]);
}
#[test]
fn point_obstacle_boost_and_as_spread_bypass() {
    let mut cells = [StarLightingCell::default(); 25];
    let mut a = array(&mut cells, 1);
    a.p.point_obstacle_boost = 1.0;
    a.cells[12].obstacle = 1;
    a.points(&[point()], [0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.25);
    a.cells.iter_mut().for_each(|c| c.light = [0.0; 3]);
    let mut p = point();
    p.as_spread = 1;
    a.points(&[p], [0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.5);
}
type Calculate = unsafe extern "C" fn(
    u32,
    usize,
    usize,
    *const StarLightingParameters,
    *mut StarLightingCell,
    usize,
    *const StarLightingSpreadLight,
    usize,
    *const StarLightingPointLight,
    usize,
    usize,
    usize,
    usize,
    usize,
) -> i32;
const ENTRYPOINTS: [Calculate; 2] = [star_lighting_calculate, star_lighting_calculate_arm_fast];

unsafe fn call(
    calculate: Calculate,
    width: usize,
    height: usize,
    p: *const StarLightingParameters,
    cells: *mut StarLightingCell,
    len: usize,
) -> i32 {
    calculate(
        1,
        width,
        height,
        p,
        cells,
        len,
        std::ptr::null(),
        0,
        std::ptr::null(),
        0,
        0,
        0,
        width,
        height,
    )
}
#[test]
fn ffi_validates_before_mutation_and_allows_null_empty_sources() {
    for calculate in ENTRYPOINTS {
        let calls_before = star_lighting_call_count();
        let mut cells = [StarLightingCell::default(); 25];
        let mut p = params();
        unsafe {
            assert_eq!(call(calculate, 5, 5, &p, cells.as_mut_ptr(), 25), 0);
            // Other Rust tests may call the ABI concurrently; only monotonicity is
            // contractual, not an exact process-global count at this instant.
            assert!(star_lighting_call_count() > calls_before);
            assert_eq!(
                call(calculate, 5, 5, std::ptr::null(), cells.as_mut_ptr(), 25),
                1
            );
            assert_eq!(call(calculate, 5, 5, &p, std::ptr::null_mut(), 25), 1);
            assert_eq!(call(calculate, 5, 5, &p, cells.as_mut_ptr(), 24), 1);
            assert_eq!(
                call(calculate, usize::MAX, 2, &p, cells.as_mut_ptr(), 25),
                1
            );
            assert_eq!(
                call(
                    calculate,
                    5,
                    5,
                    &p,
                    (cells.as_mut_ptr() as *mut u8).add(1).cast(),
                    25
                ),
                1
            );
            assert_eq!(
                call(
                    calculate,
                    5,
                    5,
                    cells.as_ptr().cast(),
                    cells.as_mut_ptr(),
                    25
                ),
                1
            );
            p.spread_max_air = 0.0;
            assert_eq!(call(calculate, 5, 5, &p, cells.as_mut_ptr(), 25), 1);
            p = params();
            // The C++ parameter accepts negative obstacle boosts (reduced shadowing).
            p.point_obstacle_boost = -0.5;
            assert_eq!(call(calculate, 5, 5, &p, cells.as_mut_ptr(), 25), 0);
            cells[4].light[2] = f32::NAN;
            assert_eq!(call(calculate, 5, 5, &p, cells.as_mut_ptr(), 25), 1);
        }
    }
}
#[test]
fn ffi_rejects_source_pointer_lengths_nonfinite_and_bad_bounds() {
    for calculate in ENTRYPOINTS {
        let mut cells = [StarLightingCell::default(); 25];
        let p = params();
        let mut source = StarLightingSpreadLight {
            position: [1.0; 2],
            value: [1.0; 3],
        };
        unsafe {
            let run = |sources, len, xmin, xmax| {
                calculate(
                    3,
                    5,
                    5,
                    &p,
                    cells.as_mut_ptr(),
                    25,
                    sources,
                    len,
                    std::ptr::null(),
                    0,
                    xmin,
                    0,
                    xmax,
                    5,
                )
            };
            let mut run = run;
            assert_eq!(run(std::ptr::null(), 1, 0, 5), 1);
            assert_eq!(run(&source, usize::MAX, 0, 5), 1);
            assert_eq!(run(&source, 1, 6, 5), 1);
            assert_eq!(run(&source, 1, 0, 6), 1);
            source.value[0] = f32::INFINITY;
            assert_eq!(run(&source, 1, 0, 5), 1);
        }
        assert!(cells.iter().all(|c| c.light == [0.0; 3]));
    }
}
#[test]
fn additive_threshold_and_hard_unit_attenuation_cutoff() {
    let mut cells = [StarLightingCell::default(); 25];
    let mut a = array(&mut cells, 1);
    a.p.point_additive = 1;
    let mut p = point();
    p.value = [0.25005; 3];
    a.points(&[p], [0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.0); // residual <= 0.0001 is not added
    p.value = [0.2502; 3];
    a.points(&[p], [0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.2502 - 0.25);
    a.cells.fill(StarLightingCell::default());
    a.p.point_max_air = 1.0;
    p.value = [2.0; 3];
    a.points(&[p], [0, 0, 5, 5]);
    assert_eq!(a.cells[17].light[0], 0.0); // attenuation >= 1 wins even with intensity > 1
}
#[test]
fn tiny_grids_and_far_sources_are_safe() {
    for width in 1..=2 {
        for height in 1..=2 {
            let mut cells = vec![StarLightingCell::default(); width * height];
            let mut a = Array::<false> {
                width,
                height,
                n: 3,
                p: params(),
                cells: &mut cells,
            };
            a.sources(&[StarLightingSpreadLight {
                position: [f32::MAX; 2],
                value: [1.0; 3],
            }]);
            a.sweeps([0, 0, width, height]);
            let mut p = point();
            p.position = [0.0; 2];
            a.points(&[p], [0, 0, width, height]);
            assert!(a
                .cells
                .iter()
                .all(|c| c.light.iter().all(|v| v.is_finite())));
        }
    }
}
