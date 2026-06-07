# Static Audit Summary - Phase 4A

## Audit Status
- **Overall Status**: `PASSED`
- **Audit Type**: 10m OpenWater Bridge Layer Synchronous Static Audit

## Detailed Checks Table

| Audit Check Identifier | Expected Condition / Value | Actual Checked Status | Result |
| :--- | :--- | :--- | :---: |
| **res10_json_exists** | `openwater_open_res10_v1.json` exists | `True` | ✅ |
| **res10_npz_exists** | `openwater_open_res10_v1.npz` exists | `True` | ✅ |
| **v1_json_unmodified** | `openwater_open_v1.json` SHA256 is unmodified | `True` | ✅ |
| **v1_npz_unmodified** | `openwater_open_v1.npz` SHA256 is unmodified | `True` | ✅ |
| **res10_cell_size_is_10** | Cell size is `10.0` meters | `True` | ✅ |
| **res10_origin_is_correct** | Origin XY is `[-400.0, 400.0]` | `True` | ✅ |
| **res10_grid_shape_is_81** | Grid shape height/width is `81` | `True` | ✅ |
| **res10_occupied_count_is_320** | Outer boundaries occupied count == `320` | `True` | ✅ |
| **res10_free_count_is_6241** | Interior free cells count == `6241` | `True` | ✅ |
| **coordinate_roundtrip_passed** | Round-trip validation for boundaries & center cell | `True` | ✅ |
| **policy_adapter_no_holoocean** | No `import holoocean` in policy adapter source | `True` | ✅ |
| **build_script_no_holoocean** | No `import holoocean` in map compiler script | `True` | ✅ |
| **policy_adapter_retired_old_params** | `sensor_range_m=25.0` etc. are retired | `True` | ✅ |
| **policy_adapter_active_new_params** | `sensor_range_m=50.0` etc. are active | `True` | ✅ |
| **no_dynamic_loader_injections**| No `sys.meta_path` dynamic loading hooks | `True` | ✅ |

## Verification Details

- **v1 Map specification hash**: `0525c4fa6d67e5779a77cec28d635f1ff8fbf899563598d250ed8fe7a6f31e6e`
- **v1 Map grid NPZ hash**: `dc9a80366ba2ccf008a9292830922f621491a9599731f84404bbe64d04bf3924`
- **Static checking scope**: Checked the active bridge directory `baseline_GP/holoocean_bridge/` and results phase directories. Retrospectively excluded historical results directories to prevent stale metrics reporting.

*Audit verified statically by execution layer.*
