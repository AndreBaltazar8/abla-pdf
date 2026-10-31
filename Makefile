ABLAC_DIR ?= $(abspath ../ablac)
COMPILER ?= $(ABLAC_DIR)/build/ablac
TESTS := tests/flate_test.ab tests/crypt_test.ab tests/writer_test.ab tests/reader_test.ab tests/signature_test.ab
TOOLS := nix-shell -p qpdf poppler-utils verapdf ghostscript

.PHONY: test test-in-shell external corpus signatures clean

test:
	nix-shell $(ABLAC_DIR)/shell.nix --run '$(MAKE) test-in-shell'

test-in-shell:
	$(COMPILER) test $(TESTS)

# qpdf, poppler, ghostscript and veraPDF on generated files.
external: test
	$(TOOLS) --run tools/check-generated.sh

# The reader against files from other producers, and fuzzing over those files.
corpus:
	tools/test-corpus.sh
	nix-shell $(ABLAC_DIR)/shell.nix --run '$(COMPILER) test tests/corpus_test.ab tests/fuzz_test.ab'

# Signatures with a throwaway certificate, checked by pdfsig, openssl and pyHanko.
signatures: test
	nix-shell $(ABLAC_DIR)/shell.nix --run '$(COMPILER) build tools/sign-file.ab -o build/sign-file'
	nix-shell -p openssl qpdf poppler-utils 'python3.withPackages(p: [p.pyhanko p.pyhanko-certvalidator])' --run tools/test-signatures.sh

clean:
	rm -rf build tests/corpus/generated
