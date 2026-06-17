# Old Direction Match Failure Reference

The 5C-4H `matched_rangefinder_beam_hit` field is diagnostic only.

- Inner target failures if old direction field is used: `6`

| Scene | Distance | Angle | Old Matched | Source Found | Hit Beams | RGB Target Angle |
|---|---:|---|---:|---:|---|---:|
| `target_left_inner_20m` | `20.0` | `left_inner` | `False` | `True` | `[2]` | `12.656` |
| `target_right_inner_20m` | `20.0` | `right_inner` | `False` | `True` | `[6]` | `-12.375` |
| `target_left_inner_35m` | `35.0` | `left_inner` | `False` | `True` | `[2]` | `12.375` |
| `target_right_inner_35m` | `35.0` | `right_inner` | `False` | `True` | `[6]` | `-12.094` |
| `target_left_inner_50m` | `50.0` | `left_inner` | `False` | `True` | `[2]` | `12.234` |
| `target_right_inner_50m` | `50.0` | `right_inner` | `False` | `True` | `[6]` | `-12.094` |

The 5C-4H matched_rangefinder_beam_hit field is a diagnostic only. Using it directly as a detection rule would create false negatives for inner-angle true targets.
