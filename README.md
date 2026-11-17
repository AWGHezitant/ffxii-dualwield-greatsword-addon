# FFXII DualWield Greatsword Addon – build source

Add-on for LettucePray's **FF12 DualWield Vaan v0.47** (Nexus). It lets greatswords show in Vaan's left hand.

## What the DLL patch does
`ff12-dualwield.dll` is LettucePray's original DLL. No new code is added. `patch_dualwield.py`:
- copies the DLL's off-hand payload (RVA 0xE430, 0xEB0 bytes) into a new `.dwgs` section,
- appends 11 (item ID, model ID) pairs to its off-hand table,
- repoints the `lea` at RVA 0x12E5 and the size at RVA 0x12EC to the new copy.

## Build
Requires Python 3 and `pip install pefile`.

1. Download FF12 DualWield Vaan v0.47 and take `x64/modules/ff12-dualwield.dll`.
2. Run:
```
python patch_dualwield.py ff12-dualwield.dll ff12-dualwield-patched.dll 1012=16A 1013=16B 1014=16C 1015=16D 1016=16E 1017=16F 1018=170 10A2=171 10A3=172 10AD=173 10C1=16F
```

## Left-hand models
`make_lefthand.py` converts a greatsword `.dae.phyre` model into a left-hand copy (mirrored position and rotation). The 10 resulting models load through the FF12 External File Loader as model IDs 0x16A–0x173.
