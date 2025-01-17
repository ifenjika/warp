GOLDEN_DIR := ./scripts/golden-testing
BATS_DIR := ./build/bats
TEMPLATES := $(wildcard $(GOLDEN_DIR)/*.template)
BATS_FILES := $(patsubst $(GOLDEN_DIR)/%.template,$(BATS_DIR)/test-%.bats,$(TEMPLATES))
TEST_FILES := $(shell find ./tests -type f ! -name '*.temp*') # exclude temporary files
SRC_FILES := $(shell find ./warp/ -type f)
KUDU_FILES := $(shell find ./warp/bin -name kudu)
PY_REQUIREMENTS := requirements.txt
NPROCS := $(shell getconf _NPROCESSORS_ONLN)

warp: .warp-activation-token
.PHONY: warp

.warp-activation-token: $(SRC_FILES) $(KUDU_FILES) ./scripts/kudu setup.py $(PY_REQUIREMENTS)
	python setup.py install
	touch .warp-activation-token

test: test_bats test_yul benchmark
.PHONY: test

test_bats: warp $(BATS_FILES) tests/cli/*.bats
	bats -j $(NPROCS) $^ $(ARGS)
.PHONY: test_bats

test_yul: warp
	mkdir -p benchmark/stats
	mkdir -p benchmark/tmp
	python -m pytest tests/ast/ -v --tb=short --workers=auto $(ARGS)
	python -m pytest scripts/yul/transpile_test.py -v --tb=short --workers=auto $(ARGS)
	python -m pytest scripts/yul/compilation_test.py -v --tb=short --workers=auto $(ARGS)
	python -m pytest tests/behaviour/ -v --tb=short --workers=auto $(ARGS)
.PHONY: test_yul

benchmark: warp
	mkdir -p benchmark/stats
	mkdir -p benchmark/tmp
	python -m pytest tests/benchmark -v --tb=short --workers=auto $(ARGS)
	python ./warp/logging/generateMarkdown.py
.PHONY: benchmark

$(BATS_DIR)/test-%.bats: \
		$(GOLDEN_DIR)/%.template \
		$(GOLDEN_DIR)/generate-bats.sh \
		$(TEST_FILES) \
		| $(BATS_DIR)
	bash $(GOLDEN_DIR)/generate-bats.sh $< > $@

$(BATS_DIR):
	mkdir -p $(BATS_DIR)

clean:
	rm -rf $(BATS_DIR)
.PHONY: clean
