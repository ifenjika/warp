GOLDEN_DIR := ./scripts/golden-testing
BATS_DIR := ./build/bats
TEMPLATES := $(wildcard $(GOLDEN_DIR)/*.template)
BATS_FILES := $(patsubst $(GOLDEN_DIR)/%.template,$(BATS_DIR)/test-%.bats,$(TEMPLATES))
TEST_FILES := $(shell find ./tests -type f ! -name '*.temp*') # exclude temporary files
SRC_FILES := $(shell find ./warp/ -type f)
PY_REQUIREMENTS := requirements.txt

warp: .warp-deps .warp-activation-token
.PHONY: warp

.warp-activation-token: $(SRC_FILES) setup.py
	python setup.py install
	touch .warp-activation-token

.warp-deps: requirements.txt
	pip install -r requirements.txt
	touch .warp-deps

test: test_bats test_yul
.PHONY: test

test_bats: warp $(BATS_FILES)
	bats -j 20 $^ $(BATS_ARGS)
.PHONY: test_bats

test_yul: warp
	python -m pytest scripts/yul/transpile_test.py -v --tb=short $(ARGS)
	python -m pytest scripts/yul/compilation_test.py -v --tb=short $(ARGS)
	python -m pytest tests/yul/ -v --tb=short $(ARGS)
.PHONY: test_yul

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
