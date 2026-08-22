## Sources and objects live in noxim3d_src/; binaries are written to the repo root.
## This delegates so `make`, `make clean` and `make -jN MODULE=noxim_variant`
## keep working from the root, as the sweep scripts expect.

MODULE ?= noxim

.PHONY: all clean depend
all:
	$(MAKE) -C noxim3d_src MODULE=$(MODULE)

clean depend:
	$(MAKE) -C noxim3d_src $@ MODULE=$(MODULE)
