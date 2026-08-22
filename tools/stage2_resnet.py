#!/usr/bin/env python3
"""ResNet-50 stage-3 bottleneck block -- model config for stage2_core.

Reproduces stage2_dnn_traffic.py byte-for-byte (data rows + CSVs); that identity
is the regression gate for the core extraction.  Production ResNet tables still
come from the frozen stage2_dnn_traffic.py -- this file is the proof and the
eventual migration path.
"""
import sys
import stage2_core as core

MODEL_TAG = "resnet50_bottleneck3"
CYCLES_PER_MAC = 2e-4       # conv1 shortest phase 5,138 = 7.9x DP_CYCLE (648);
                            # matches the cpm of the published STAGE3-MAPPING-FINDINGS
                            # runs (t_period 38,536) so ResNet stays comparable to them

XB = 128                    # IMC crossbar dimension (XB x XB)
FMAP_H, FMAP_W = 14, 14     # feature map of ResNet-50 stage 3, stride 1

# (name, k, Cin, Cout, kind)  -- weight matrix is (k*k*Cin) x Cout
LAYERS = [
    ("conv1",    1,  512,  256, "conv"),
    ("conv2",    3,  256,  256, "conv"),
    ("conv3",    1,  256, 1024, "conv"),
    ("shortcut", 1,  512, 1024, "shortcut"),
]

# grid = (R, C) per layer; boxes = (x0,y0,z0,sx,sy,sz), holding exactly R*C cells.
CONFIGS = {
    "6x6x3": dict(
        dims=(6, 6, 3),
        grid={"conv1": (6, 2), "conv2": (18, 2), "conv3": (3, 8), "shortcut": (4, 9)},
        boxes={"conv1":    (0, 0, 0, 2, 2, 3),   # 12
               "conv2":    (2, 0, 0, 4, 3, 3),   # 36
               "conv3":    (0, 2, 0, 2, 4, 3),   # 24
               "shortcut": (2, 3, 0, 4, 3, 3)},  # 36  -> 108
    ),
    "6x6x3_base": dict(
        dims=(6, 6, 3),
        grid={"conv1": (4, 2), "conv2": (18, 2), "conv3": (2, 8), "shortcut": (4, 8)},
        boxes={"shortcut": (0, 0, 0, 4, 4, 2),   # 32
               "conv2":    (4, 0, 0, 2, 6, 3),   # 36
               "conv3":    (0, 0, 2, 4, 4, 1),   # 16
               "conv1":    (0, 4, 0, 4, 2, 1)},  #  8  -> 92
    ),
    "7x7x3": dict(
        dims=(7, 7, 3),
        grid={"conv1": (4, 2), "conv2": (18, 2), "conv3": (2, 8), "shortcut": (4, 8)},
        boxes={"conv2":    (0, 0, 0, 3, 4, 3),   # 36
               "shortcut": (3, 0, 0, 4, 4, 2),   # 32
               "conv3":    (3, 0, 2, 4, 4, 1),   # 16
               "conv1":    (0, 4, 0, 2, 2, 2)},  #  8  -> 92, 55 tile-free
    ),
}

# The one projection shortcut: reads the block input, its result is added at
# conv3's accumulators, and it spans the whole block pass.
RESIDUALS = [
    dict(name="shortcut", type="proj", layer="shortcut",
         **{"from": "block_input"}, add_at="conv3", span=("conv1", "conv3")),
]

if __name__ == "__main__":
    core.run(sys.modules[__name__])
