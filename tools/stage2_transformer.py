#!/usr/bin/env python3
"""Transformer (BERT/ViT-Base) single encoder block -- model config for stage2_core.

One encoder block at 256x256 crossbars, 8 crossbars/tile -> 108 tiles filling
6x6x3 exactly (MAPPING-FORMULATION.md SS4 sizing decision; originally
docs/archive/STAGE3-MAPPING-FINDINGS.md).  Two
residuals per block (attention bypass + FFN bypass), modelled as identity
(weight-free, traffic only), the direct analogue of ResNet's identity shortcuts.

Placement is the deliberate UNOPTIMISED baseline (STAGE2.md SS9.2) -- the control.
Interior / NSGA placement is the mapping stage's job, scored downstream.

Pre-existing modelling limitation (shared with stage2_dnn_full.py): q/k/v/o are a
sequential trunk chain and the QK^T / A.V attention matmuls are not represented --
only the four projection matmuls carry weights.
"""
import sys
import stage2_core as core

MODEL_TAG = "transformer_encoder1"
CYCLES_PER_MAC = 1e-4

XB = 256                    # 256x256 crossbar: one block fills 6x6x3 at 8 xb/tile
FMAP_H, FMAP_W = 197, 1     # "feature map" = token sequence length (seq); HW = 197

d, ff = 768, 3072
# (name, k, Cin, Cout, kind)  -- all k=1 matmuls
LAYERS = [
    ("q",   1, d,  d,  "conv"),
    ("k",   1, d,  d,  "conv"),
    ("v",   1, d,  d,  "conv"),
    ("o",   1, d,  d,  "conv"),
    ("ff1", 1, d,  ff, "conv"),
    ("ff2", 1, ff, d,  "conv"),
]

# grid = (R, C) per layer at XB=256; boxes = (x0,y0,z0,sx,sy,sz) tiling 6x6x3.
#   q,k,v,o: 768x768   -> R=3,C=3  -> 9 tiles each (36 total)
#   ff1:     768x3072  -> R=3,C=12 -> 36 tiles
#   ff2:     3072x768  -> R=12,C=3 -> 36 tiles   (total 108)
CONFIGS = {
    "6x6x3": dict(
        dims=(6, 6, 3),
        grid={"q": (3, 3), "k": (3, 3), "v": (3, 3), "o": (3, 3),
              "ff1": (3, 12), "ff2": (12, 3)},
        boxes={"q":   (0, 0, 0, 3, 1, 3),   # 9   x0-2 y0
               "k":   (3, 0, 0, 3, 1, 3),   # 9   x3-5 y0
               "v":   (0, 1, 0, 3, 1, 3),   # 9   x0-2 y1
               "o":   (3, 1, 0, 3, 1, 3),   # 9   x3-5 y1
               "ff1": (0, 2, 0, 6, 2, 3),   # 36  y2-3
               "ff2": (0, 4, 0, 6, 2, 3)},  # 36  y4-5  -> 108
    ),
}

# q/k/v are PARALLEL: all three read the block input, none depends on another.
# `o` should consume A.V; the attention core (QK^T / softmax / A.V) carries no
# weights and is not modelled (see docstring), so `v` stands in for it.
DEPS = {"q": ["block_input"], "k": ["block_input"], "v": ["block_input"],
        "o": ["v"], "ff1": ["o"], "ff2": ["ff1"]}

# Two identity residuals per encoder block.
#   attention: block input   -> attention output-projection (o) accumulators
#   FFN:       attention out  -> FFN second-matmul (ff2) accumulators
RESIDUALS = [
    dict(name="attn_res", type="identity",
         **{"from": "block_input"}, add_at="o",   span=("q",   "o")),
    dict(name="ffn_res",  type="identity",
         **{"from": "o"},           add_at="ff2", span=("ff1", "ff2")),
]

if __name__ == "__main__":
    core.run(sys.modules[__name__])
