#!/usr/bin/env python3
"""DeiT-S / ViT-Small single encoder block -- model config for stage2_core.

Same block structure as stage2_transformer.py, at HALF the width and HALF the
crossbar size.  The point is to put the transformer on the SAME 128x128 crossbar
as ResNet-50 and VGG-16, so crossbar size stops being a per-workload variable.

  ViT-Base  d=768,  ff=3072  at XB=256  -> 108 tiles   (what stage2_transformer does)
  ViT-Base  d=768,  ff=3072  at XB=128  -> 432 tiles   (does not fit 6x6x3)
  DeiT-S    d=384,  ff=1536  at XB=128  -> 108 tiles   (this file)

The tile grid is *identical* to the ViT-Base/XB=256 config -- q/k/v/o 3x3, ff1
3x12, ff2 12x3 -- so `grid` and `boxes` are reused unchanged and the reduction
depths are the same (2,2,2,2,2,11).  Only the payload volume halves.  Expect the
reduce/scatter ratio to be unchanged: reduce ~ Cout, scatter ~ Cin, and both
halve together.

At 128 rows the 16-bit partial sum of CROSSBAR-ADC-PACKING.md SS2.2 is derivable
(8-bit ADC per weight bit-slice, shift-and-add over 8 bit-planes); at 256 rows it
is not (17 bits needed).  So this config is the one that supports
DNN_BYTES_PER_PSUM=2 without an explicit-truncation caveat.

Dimensions: DeiT-S (Touvron et al., ICML 2021) -- d_model 384, MLP ratio 4 ->
1536, 6 heads, 12 layers, 197 tokens.  NOT the original ViT paper, which defines
only Base/Large/Huge.
"""
import sys

import stage2_core as core

MODEL_TAG = "vitsmall_encoder1"
CYCLES_PER_MAC = 1e-4

XB = 128                    # same crossbar as ResNet-50 and VGG-16
FMAP_H, FMAP_W = 197, 1     # "feature map" = token sequence length; HW = 197

d, ff = 384, 1536           # DeiT-S: d_model 384, MLP ratio 4
# (name, k, Cin, Cout, kind)  -- all k=1 matmuls
LAYERS = [
    ("q",   1, d,  d,  "conv"),
    ("k",   1, d,  d,  "conv"),
    ("v",   1, d,  d,  "conv"),
    ("o",   1, d,  d,  "conv"),
    ("ff1", 1, d,  ff, "conv"),
    ("ff2", 1, ff, d,  "conv"),
]

# grid = (R, C) per layer at XB=128; boxes = (x0,y0,z0,sx,sy,sz) tiling 6x6x3.
#   q,k,v,o: 384x384   -> R=3,C=3  -> 9 tiles each (36 total)
#   ff1:     384x1536  -> R=3,C=12 -> 36 tiles
#   ff2:     1536x384  -> R=12,C=3 -> 36 tiles   (total 108)
# Identical to the ViT-Base/XB=256 grid -- reused verbatim.
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
# weights and is not modelled, so `v` stands in for it.
DEPS = {"q": ["block_input"], "k": ["block_input"], "v": ["block_input"],
        "o": ["v"], "ff1": ["o"], "ff2": ["ff1"]}

# Two identity residuals per encoder block.
RESIDUALS = [
    dict(name="attn_res", type="identity",
         **{"from": "block_input"}, add_at="o",   span=("q",   "o")),
    dict(name="ffn_res",  type="identity",
         **{"from": "o"},           add_at="ff2", span=("ff1", "ff2")),
]

if __name__ == "__main__":
    core.run(sys.modules[__name__])
