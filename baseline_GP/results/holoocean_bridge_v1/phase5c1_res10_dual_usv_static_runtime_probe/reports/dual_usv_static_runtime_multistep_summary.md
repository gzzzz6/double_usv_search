# Phase 5C-1 Runtime-Only Multistep Probe Summary

## Configuration
- Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Assignment: `coordinated`
- Target Motion: `static`
- Map: `81x81` at `10.0` m
- Episode Seed: `0`
- Max Steps: `240`

## Result
- Terminated Reason: `all_found`
- Initial All Found: `False`
- Completed Steps: `32`
- Final Found Count: `1`
- Hit Branch Covered: `True`
- GP n_obs Initial/Final: `48` -> `400`
- Trace Rows: `32`

## Notes
- Runtime-only probe: no HoloOcean import or env control calls.
- The step loop mirrors `marine_knownmap_runtime_2usv.py` step_targets -> predict_intensity -> assignment -> execute_next_step -> team belief update.
