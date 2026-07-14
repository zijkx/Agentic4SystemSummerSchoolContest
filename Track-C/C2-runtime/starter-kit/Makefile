CXX ?= g++
CC ?= cc
CXXFLAGS ?= -O2 -g -std=c++17 -fPIC -Wall -Wextra -Wpedantic -ffp-contract=off -fvisibility=hidden
CPPFLAGS ?= -Iinclude

RUNTIME := libaec.so
RUNTIME_SOURCES := $(wildcard src/*.cpp)
RUNTIME_HEADERS := $(wildcard src/*.h) include/aec_runtime.h include/aec_device_abi.h include/aec_isa.h
RUNTIME_MAP := src/libaec.map
EXAMPLES := \
	bin/01_device_query \
	bin/02_isa_encoding \
	bin/03_vector_add \
	bin/04_stream_event \
	bin/05_fp32_gemm \
	bin/06_registered_copy

.PHONY: all examples public-test public-cases clean

all: $(RUNTIME)

$(RUNTIME): $(RUNTIME_SOURCES) $(RUNTIME_HEADERS) $(RUNTIME_MAP) lib/libaec_device.so
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -shared $(RUNTIME_SOURCES) -o $@ -pthread \
		-Wl,--version-script=$(RUNTIME_MAP)

bin/%: examples/%.c $(RUNTIME)
	mkdir -p $(@D)
	$(CC) $(CPPFLAGS) -O2 -g -std=c11 -Wall -Wextra -Wpedantic $< -o $@ \
		-L. -laec -Llib -Wl,--no-as-needed -laec_device -Wl,--as-needed \
		-Wl,-rpath,'$$ORIGIN/..' -Wl,-rpath,'$$ORIGIN/../lib'

examples: $(EXAMPLES)

public-test: all
	python3 grader/public_grade.py --submission . --profile public

public-cases: all
	python3 cases/run_all.py --submission .

clean:
	rm -rf bin $(RUNTIME)
