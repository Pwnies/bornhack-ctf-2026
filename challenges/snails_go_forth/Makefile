# Build for "The Great Escargot" (snails_go_forth).
#
# Pipeline:
#   flag.txt ──author.fs──▶ CIPHER block ──splice──▶ escargot.dev.fs
#                                                          │
#                                                    obfuscate.py
#                                                          ▼
#                                                     escargot.fs  (distributed)
#
# To change the flag: edit flag.txt, run `make`. That regenerates the embedded
# ciphertext, splices it into escargot.dev.fs, rebuilds escargot.fs, and runs
# the regression tests. No hand-editing of ciphertext or test patterns.
#
# Tooling (gforth, python3) comes from the flake dev shell via nix-shell, so
# `make` works from a bare shell. If you are already inside `nix develop` (or
# otherwise have gforth+python3 on PATH), run:  make NIXRUN='bash -c'

NIXRUN ?= nix-shell -p gforth python3 --run

DEV    := escargot.dev.fs
OUT    := escargot.fs
FLAG   := flag.txt
INC    := cipher.inc

# Player-facing handout. Deliberately excludes the dev source, author.fs,
# flag.txt and obfuscate.py — those would spoil the challenge.
DIST_NAME  := snails_go_forth
DIST_FILES := $(OUT) chacha20.fs
TARBALL    := $(DIST_NAME).tar.gz

.PHONY: all cipher build test run dist clean

all: build test dist

# Regenerate the CIPHER block from flag.txt and splice it into the dev source.
# author.fs self-checks the round-trip and exits non-zero if encryption breaks.
# Deterministic: re-running with an unchanged flag leaves $(DEV) byte-identical.
cipher: $(FLAG) author.fs chacha20.fs
	$(NIXRUN) 'gforth author.fs' > $(INC)
	awk '/^create CIPHER/{while((getline line < "$(INC)")>0)print line;skip=1;next} skip&&/constant #FLAG/{skip=0;next} skip{next} {print}' $(DEV) > $(DEV).tmp
	mv $(DEV).tmp $(DEV)
	rm -f $(INC)

# Obfuscate the dev source into the distributed challenge file.
build: cipher obfuscate.py
	$(NIXRUN) 'python3 obfuscate.py'

# Run the regression suite against the distributed file.
test: build
	$(NIXRUN) './test.sh $(OUT)'

# Play the (readable) dev version locally.
run: cipher
	$(NIXRUN) 'gforth $(DEV)'

# Package the player-facing files into $(TARBALL), under a $(DIST_NAME)/ prefix.
dist: build
	rm -rf $(DIST_NAME) $(TARBALL)
	mkdir $(DIST_NAME)
	cp $(DIST_FILES) $(DIST_NAME)/
	tar czf $(TARBALL) $(DIST_NAME)
	rm -rf $(DIST_NAME)
	@echo "wrote $(TARBALL):"; tar tzf $(TARBALL)

clean:
	rm -f $(INC) $(DEV).tmp $(TARBALL)
	rm -rf $(DIST_NAME)
