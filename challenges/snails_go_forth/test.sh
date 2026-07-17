#!/usr/bin/env bash
# Regression tests for The Great Escargot. Usage: ./test.sh [file.fs]
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FS="${1:-escargot.fs}"
# Flag comes from flag.txt (single source of truth); escape ERE metacharacters
# so it can be used as a grep pattern.
FLAG="$(cat "$HERE/flag.txt")"
FLAG_RE="$(printf '%s' "$FLAG" | sed 's/[][\\.^$*+?(){}|/]/\\&/g')"
pass=0; fail=0
run(){ printf '%b' "$1" | gforth "$FS" 2>/dev/null; }
check(){ # desc, input, grep-pattern
  local d="$1" in="$2" pat="$3"
  if run "$in" | grep -qiE "$pat"; then echo "  PASS: $d"; pass=$((pass+1))
  else echo "  FAIL: $d"; fail=$((fail+1)); fi
}
refute(){ # desc, input, grep-pattern (must NOT appear)
  local d="$1" in="$2" pat="$3"
  if run "$in" | grep -qiE "$pat"; then echo "  FAIL: $d"; fail=$((fail+1))
  else echo "  PASS: $d"; pass=$((pass+1)); fi
}

WIN='left\ndown\ndown\ndown\ndown\nright\nright\nnext\nleft\ndown\ndown\nright\ndown\nnext\ndown\ndown\ndown\nright\nright\nright\nright\nright\nup\nnext\ndown\nleft\n'

echo "== The Great Escargot regression =="
check "winning walkthrough reveals the flag"       "$WIN" "$FLAG_RE"
check "win screen prints"                          "$WIN" "the colony feasts"
check "wall block names obstacle (rockery)"        'right\n' "rockery"
refute "wall block does NOT re-describe tile"      'right\n' "bucket's shadow.*rockery|rockery.*Ahead: the whole green night"
check "edge block names garden's edge"             'up\n' "garden's edge"
check "crossing triggers fail screen"              'left\ndown\nup\n' "wink of crossed slime"
check "fail then 'n' quits"                        'left\ndown\nup\nn\n' "creeps back to the bucket"
check "fail then 'y' restarts"                     'left\ndown\nup\ny\n' "dew is still wet"
check "worm easter egg"                            'left\ndown\ndown\nright\n' "SNAILOR"
check "disco easter egg (no 'disco' word)"         'next\nup\n' "mirrored ball"
check "ladybird easter egg"                        'next\nnext\nnext\ndown\ndown\n' "ladybird is sunbathing"
check "wrong food is a no-op message"              'next\nnext\ndown\ndown\nright\nright\nright\n' "not what you came for"
check "unknown word rebuffed"                      'xyzzy\n' "don't know that word"
check "help screen"                                'help\n' "crawl one tile"
check "quit command"                               'quit\n' "creeps back to the bucket"
check "removed alias 'n' is rejected"              'n\n' "don't know that word"
check "removed alias 'd' is rejected"              'd\n' "don't know that word"
refute "removed alias 'n' does NOT switch snail"   'n\n' "wake in Turbo"
check "homed snail cannot be over-moved"           'left\ndown\ndown\ndown\ndown\nright\nright\nup\n' "curled happily on your supper"
check "auto-describe on move"                      'left\n' "hard standing"
check "POV inner voice on next"                    'next\n' "Where were we"
check "EOF (no quit) exits cleanly"                'left\n' "creeps back to the bucket"

echo "== $pass passed, $fail failed =="
exit $((fail>0))
