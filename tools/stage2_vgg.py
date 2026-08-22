#!/usr/bin/env python3
"""VGG-16 block 3 (the 256-channel conv group) -- model config for stage2_core.

Three consecutive 3x3 convs at 128x128 crossbars -> 90 tiles on 6x6x3 (83%, 18
nodes tile-free), matched to ResNet's 92-tile footprint so the two run on the same
mesh at the same density with no geometry confound (MAPPING-FORMULATION.md SS4
sizing decision; originally docs/archive/STAGE3-MAPPING-FINDINGS.md).

VGG is a plain sequential CNN: NO skip connections, so RESIDUALS is empty.  Its
hotspot structure is different from ResNet's -- width-2 everywhere, three deep
reductions (R=9/18) into two accumulators each, firing in adjacent phases (six hot
sinks total).  That contrast is the point of including it.

Placement is the deliberate UNOPTIMISED baseline (STAGE2.md SS9.2) -- the control.
"""
import sys
import stage2_core as core

MODEL_TAG = "vgg16_block3"
CYCLES_PER_MAC = 1e-4

XB = 128                    # VGG stays at 128x128 (ResNet-comparable)
FMAP_H, FMAP_W = 56, 56     # VGG-16 block-3 feature map (before the next pool)

# (name, k, Cin, Cout, kind) -- 3x3 convs; weight matrix (9*Cin) x Cout
#   conv5: 1152x256 -> R=9,  C=2 -> 18 tiles
#   conv6: 2304x256 -> R=18, C=2 -> 36 tiles
#   conv7: 2304x256 -> R=18, C=2 -> 36 tiles   (total 90)
LAYERS = [
    ("conv5", 3, 128, 256, "conv"),
    ("conv6", 3, 256, 256, "conv"),
    ("conv7", 3, 256, 256, "conv"),
]

# grid = (R, C) per layer at XB=128 (base grids, 8 crossbars/tile);
# boxes = (x0,y0,z0,sx,sy,sz) tiling 90 of the 108 nodes, 18 left tile-free.
CONFIGS = {
    "6x6x3": dict(
        dims=(6, 6, 3),
        grid={"conv5": (9, 2), "conv6": (18, 2), "conv7": (18, 2)},
        boxes={"conv6": (0, 0, 0, 6, 2, 3),   # 36  y0-1
               "conv7": (0, 2, 0, 6, 2, 3),   # 36  y2-3
               "conv5": (0, 4, 0, 3, 2, 3)},  # 18  x0-2 y4-5  -> 90, 18 tile-free
    ),
}

# VGG has no skip connections.
RESIDUALS = []

if __name__ == "__main__":
    core.run(sys.modules[__name__])
