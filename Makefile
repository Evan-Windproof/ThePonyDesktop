.DEFAULT_GOAL := all
# SPDX-License-Identifier: GPL-3.0-or-later
HOOFTTY ?= ../HoofTTY
CC ?= cc
.PHONY: all integrate check test run check-integration version check-version
version:
	@cat VERSION
check-version:
	python3 scripts/version.py
check-integration:
	python3 tests/integration.py "$(HOOFTTY)"
all: integrate
	$(MAKE) -C $(HOOFTTY) iso check
integrate: check-version
	./integration/apply.sh "$(HOOFTTY)"
check: integrate
	mkdir -p build
	$(CC) -std=c11 -O2 -Wall -Wextra -Werror -I$(HOOFTTY)/include -I$(HOOFTTY)/third_party/limine tests/pixels.c $(HOOFTTY)/kernel/drivers/framebuffer.c -o build/pixels-test
	./build/pixels-test
	$(MAKE) -C $(HOOFTTY) build/runtime-test build/framebuffer-test build/memory-span-test
	$(HOOFTTY)/build/runtime-test
	$(HOOFTTY)/build/framebuffer-test
	$(HOOFTTY)/build/memory-span-test
test: check-integration all check
	python3 tests/qemu_smoke.py "$(HOOFTTY)"
run: all
	$(MAKE) -C $(HOOFTTY) run
