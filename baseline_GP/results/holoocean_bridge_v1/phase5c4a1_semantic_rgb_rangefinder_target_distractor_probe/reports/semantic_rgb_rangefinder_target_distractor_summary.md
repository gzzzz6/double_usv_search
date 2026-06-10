# Phase 5C-4A-1 Semantic/RGB/RangeFinder Target-Distractor Summary

## Status
- Probe Completed: `True`
- Semantic Can Distinguish Target From Distractor: `False`
- RGB Can Distinguish Target From Distractor: `True`
- RangeFinder Object Presence Supported: `True`
- Composite Sensor Detection Supported: `True`
- RGB Available As Visual Evidence: `True`
- RangeFinder Available As Range Evidence: `True`
- All Detection Events Correct: `True`

## Signature
- Semantic Target Signature Colors: `[]`
- Semantic Distractor Signature Colors: `[]`
- Semantic Target/Distractor Disjoint: `False`
- RGB Target Signature Colors: `['128,128,128,255', '128,128,96,255', '128,64,32,255', '128,96,64,255', '128,96,96,255', '160,160,192,255', '160,96,64,255', '192,160,96,255', '224,160,128,255', '224,192,128,255', '96,64,32,255', '96,64,64,255', '96,96,64,255']`
- RGB Distractor Signature Colors: `['224,192,192,255']`
- RGB Target/Distractor Disjoint: `True`

## Notes
- Runtime search is not imported.
- Search decision algorithms remain frozen.
- SemanticSegmentationCamera is recorded as identity evidence only if it produces a target-specific signature.
- RGBCamera provides visual identity evidence through an audited RGB difference signature.
- RangeFinderSensor is range evidence only, not target identity.
- Sonar is disabled.
