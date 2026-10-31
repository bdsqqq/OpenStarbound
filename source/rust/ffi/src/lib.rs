//! The engine's single Rust static archive owns the unmangled C ABI exports.
//! Kernels remain rlibs so linking another kernel cannot add another Rust runtime.
mod lru_cache;
pub use lru_cache::{sb_lru_count, sb_lru_run, SbLruHost, SbLruReply, SbLruRequest};
mod ttl_cache;
pub use ttl_cache::{sb_ttl_count, sb_ttl_run, SbTtlHost, SbTtlReply, SbTtlRequest};
mod weighted_pool;
pub use weighted_pool::{sb_wp_count, sb_wp_run, SbWpHost, SbWpReply, SbWpRequest};
mod id_map;
pub use id_map::{sb_idmap_count, sb_idmap_run, SbIdMapHost, SbIdMapReply, SbIdMapRequest};
mod bimap;
pub use bimap::{sb_bimap_count, sb_bimap_run, SbBiMapHost, SbBiMapReply, SbBiMapRequest};
mod flat_hash_table;
pub use flat_hash_table::{sb_flat_hash_count, sb_flat_hash_run, SbFlatHashReply};
mod uuid;
pub use uuid::{sb_uuid_compare, sb_uuid_count, sb_uuid_from_bytes, sb_uuid_hash};
mod ordered_set;
pub use ordered_set::{
    sb_ordered_set_count, sb_ordered_set_run, sb_ordered_set_select, sb_ordered_set_select_count,
    sb_set_count, sb_set_run, sb_set_select, sb_set_select_count, sb_set_global_count,
};
mod static_vector;
pub use static_vector::{
    sb_static_vector_count, sb_static_vector_run, SbStaticVectorHost,
    SbStaticVectorReply, SbStaticVectorRequest,
};

mod string_view;
pub use string_view::{star_string_view_call_count, star_string_view_run, StarStringViewHost};
mod file;
pub use file::{star_file_call_count, star_file_run, StarFileHost};

mod host_address;
pub use host_address::{star_host_address_call_count, star_host_address_run, StarHostAddressHost};

mod option_parser;
pub use option_parser::{
    star_option_parser_call_count, star_option_parser_run, StarOptionParserHost,
};

mod zstd;
pub use zstd::{star_zstd_call_count, star_zstd_run, StarZstdHost};

mod compression;
pub use compression::{star_compression_call_count, star_compression_run, StarCompressionHost};

mod text_scan;
pub use text_scan::{star_text_scan_call_count, star_text_scan_process, StarTextScanHost};

mod random_mwc;
pub use random_mwc::{
    star_random_mwc_add_entropy, star_random_mwc_call_count, star_random_mwc_init,
    star_random_mwc_next,
};

mod asset_path;
pub use asset_path::{
    star_asset_path_call_count, star_asset_path_filename_range, star_asset_path_split,
    StarAssetPathRange, StarAssetPathSplit,
};

mod json_path;
pub use json_path::{star_json_path_call_count, star_json_path_parse, StarJsonPathHost};

mod json_patch;
pub use json_patch::{star_json_patch_call_count, star_json_patch_run, StarJsonPatchHost};

mod shell;
pub use shell::{star_shell_call_count, star_shell_tokenize, StarShellClassify, StarShellEmit};

mod unicode;
pub use unicode::*;

mod bytes;
pub use bytes::{star_bytes_call_count, star_bytes_transform};

mod vlq;
pub use vlq::{
    star_vlq_call_count, star_vlq_read_i, star_vlq_read_u, star_vlq_size_i, star_vlq_size_u,
    star_vlq_write_i, star_vlq_write_u, StarVlqRead, StarVlqWrite,
};

mod sha256;
pub use sha256::{
    star_sha256_call_count, star_sha256_finalize, star_sha256_init, star_sha256_oneshot,
    star_sha256_update, StarSha256State,
};

mod encode;
pub use encode::{star_encode, star_encode_call_count};

mod line_query;
pub use line_query::{star_line_query_call_count, star_line_query_f32, star_line_query_f64};

mod blocks_along_line;
pub use blocks_along_line::{
    star_blocks_along_line_call_count, star_blocks_along_line_f32, star_blocks_along_line_f64,
};

pub use star_lighting::{
    StarLightingCell, StarLightingParameters, StarLightingPointLight, StarLightingSpreadLight,
};

#[no_mangle]
pub extern "C" fn star_lighting_call_count() -> u64 {
    star_lighting::star_lighting_call_count()
}

/// Forwards the precise ABI without changing validation, panic containment or receipts.
///
/// # Safety
/// Nonempty pointers must refer to initialized allocations of the declared sizes.
/// Cells must be writable and exclusively borrowed for the duration of the call.
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn star_lighting_calculate(
    channels: u32,
    width: usize,
    height: usize,
    parameters: *const StarLightingParameters,
    cells: *mut StarLightingCell,
    cells_len: usize,
    spread_lights: *const StarLightingSpreadLight,
    spread_len: usize,
    point_lights: *const StarLightingPointLight,
    point_len: usize,
    x_min: usize,
    y_min: usize,
    x_max: usize,
    y_max: usize,
) -> i32 {
    star_lighting::star_lighting_calculate(
        channels,
        width,
        height,
        parameters,
        cells,
        cells_len,
        spread_lights,
        spread_len,
        point_lights,
        point_len,
        x_min,
        y_min,
        x_max,
        y_max,
    )
}

/// Forwards the production ARM expression policy with the same ABI contracts.
///
/// # Safety
/// Identical allocation and exclusive-borrow requirements to [star_lighting_calculate].
#[no_mangle]
#[allow(clippy::too_many_arguments)]
pub unsafe extern "C" fn star_lighting_calculate_arm_fast(
    channels: u32,
    width: usize,
    height: usize,
    parameters: *const StarLightingParameters,
    cells: *mut StarLightingCell,
    cells_len: usize,
    spread_lights: *const StarLightingSpreadLight,
    spread_len: usize,
    point_lights: *const StarLightingPointLight,
    point_len: usize,
    x_min: usize,
    y_min: usize,
    x_max: usize,
    y_max: usize,
) -> i32 {
    star_lighting::star_lighting_calculate_arm_fast(
        channels,
        width,
        height,
        parameters,
        cells,
        cells_len,
        spread_lights,
        spread_len,
        point_lights,
        point_len,
        x_min,
        y_min,
        x_max,
        y_max,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ptr::{null, null_mut};

    #[test]
    fn exports_share_kernel_types_status_and_counter() {
        // These are the kernel's actual types, not a second set of ABI declarations.
        let parameters = star_lighting::StarLightingParameters {
            spread_passes: 0,
            spread_max_air: 5.0,
            spread_max_obstacle: 2.0,
            point_max_air: 5.0,
            point_max_obstacle: 2.0,
            point_obstacle_boost: 0.0,
            point_additive: 0,
        };
        let before = star_lighting_call_count();
        for calculate in [star_lighting_calculate, star_lighting_calculate_arm_fast] {
            let mut cells = [star_lighting::StarLightingCell::default(); 9];
            cells[4].light[0] = 1.0;
            let status = unsafe {
                calculate(
                    1,
                    3,
                    3,
                    &parameters,
                    cells.as_mut_ptr(),
                    9,
                    null(),
                    0,
                    null(),
                    0,
                    1,
                    1,
                    2,
                    2,
                )
            };
            assert_eq!(status, 0);
            assert_eq!(cells[4].light, [1.0, 0.0, 0.0]);
            let invalid = unsafe {
                calculate(
                    2,
                    3,
                    3,
                    &parameters,
                    null_mut(),
                    9,
                    null(),
                    0,
                    null(),
                    0,
                    1,
                    1,
                    2,
                    2,
                )
            };
            assert_eq!(invalid, 1);
        }
        assert_eq!(star_lighting_call_count(), before + 2);
        assert_eq!(star_lighting::star_lighting_call_count(), before + 2);
    }
}

mod data_stream;
pub use data_stream::{star_data_stream_call_count, star_data_stream_run, StarDataStreamHost};

mod buffer;
pub use buffer::{star_buffer_call_count, star_buffer_run, StarBufferHost};

mod io_device;
pub use io_device::{star_io_device_call_count, star_io_device_run, StarIODeviceHost};

mod byte_array;
pub use byte_array::{star_byte_array_call_count, star_byte_array_run, StarByteArrayHost};

mod path_embed;
