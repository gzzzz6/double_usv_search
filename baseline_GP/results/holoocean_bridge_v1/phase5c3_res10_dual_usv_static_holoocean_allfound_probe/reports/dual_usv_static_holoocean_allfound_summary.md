# Phase 5C-3 HoloOcean All Found Probe Summary

## Configuration
- Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Assignment: `coordinated`
- Target Motion: `static`
- Map: `81x81` at `10.0` m
- Episode Seed: `0`
- Max Policy Steps: `40`
- Expected Runtime All Found Step: `32`

## Result
- Terminated Reason: `all_found`
- Completed Policy Steps: `32`
- Total Physical Ticks: `2728`
- Initial All Found: `False`
- Final Found Count: `1`
- Hit Branch Covered: `True`
- GP n_obs Initial/Final: `48` -> `400`
- Min Inter-Vessel Distance: `100.00` m
- Fallback Count Total: `0`

## Notes
- This probe requires the static target hit branch and all_found termination.
- Runtime state movement uses final HoloOcean projected cells.
