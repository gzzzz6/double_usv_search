# Phase 5C-3 HoloOcean All Found Visual Runner Summary

## Configuration
- Policy: `marine_knownmap_path_v2_infosampled_2usv`
- Assignment: `coordinated`
- Target Motion: `static`
- Map: `81x81` at `10.0` m
- Episode Seed: `0`
- Max Policy Steps: `40`
- Expected Runtime All Found Step: `32`
- Main Agent: `sv0`
- Visual Camera: `FrontRGBCamera` (`320x240` at `5` Hz)
- Visual Camera Used For Detection: `False`

## Result
- Terminated Reason: `all_found`
- Completed Policy Steps: `32`
- Total Physical Ticks: `2742`
- Initial All Found: `False`
- Final Found Count: `1`
- Hit Branch Covered: `True`
- GP n_obs Initial/Final: `48` -> `400`
- Min Inter-Vessel Distance: `100.00` m
- Fallback Count Total: `0`

## Notes
- This is a visual-only runner derived from Phase 5C-3.
- The original Phase 5C-3 audited outputs are not overwritten by this script.
- Use `H`, `Tab`, `C`, and `V` in the HoloOcean viewport to inspect agents and camera modes.
- This probe requires the static target hit branch and all_found termination.
- Runtime state movement uses final HoloOcean projected cells.
