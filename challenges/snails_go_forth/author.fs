\ author.fs — compute the embedded ciphertext for the flag.
\ Reads the plaintext flag from ./flag.txt (the single source of truth) and
\ prints, on stdout, the exact Forth block that lives in escargot.dev.fs:
\
\     create CIPHER
\       <byte> c,
\       ...
\     <len> constant #FLAG
\
\ The Makefile captures that block and splices it into escargot.dev.fs, so the
\ flag never has to be pasted in by hand. On success nothing goes to stderr; a
\ broken round-trip aborts loudly (non-zero exit) so `make` fails.
\
\ Run manually: gforth author.fs   (prints the block; use `make cipher` normally)
require ./chacha20.fs

\ Canonical 36-cell owner coloring (row-major, idx=row*6+col).
\ 0=none/wall 1=A/Gary 2=B/Turbo 3=C/Pearl 4=D/Brian
create COLOR
  0 c, 1 c, 1 c, 0 c, 0 c, 0 c,   \ row0
  0 c, 1 c, 0 c, 2 c, 2 c, 4 c,   \ row1
  3 c, 1 c, 0 c, 2 c, 4 c, 4 c,   \ row2
  3 c, 1 c, 0 c, 2 c, 2 c, 0 c,   \ row3
  3 c, 1 c, 1 c, 1 c, 2 c, 3 c,   \ row4
  3 c, 3 c, 3 c, 3 c, 3 c, 3 c,   \ row5

create BUF 64 allot          \ working buffer (ciphertext, then decrypted again)
create PT  64 allot          \ untouched plaintext copy, for the round-trip check
variable #flag

\ strip trailing CR/LF from a slurped string
: chomp ( addr len -- addr len' )
  begin
    dup 0> if 2dup + 1- c@ dup 10 = swap 13 = or else false then
  while 1- repeat ;

: read-flag ( -- )
  s" flag.txt" slurp-file chomp   \ ( addr len )
  {: a n :}
  n #flag !
  a BUF n move
  a PT  n move ;

\ derive ChaCha20 key+nonce from the canonical coloring: key=COLOR[0..31], nonce=COLOR[24..35]
: derive ( -- )  COLOR  COLOR 24 +  0 chacha20-init ;

: emit-cipher ( -- )
  ." create CIPHER" cr
  BUF #flag @ bounds ?do
    ."   " i c@ 3 .r ."  c," cr
  loop
  #flag @ 0 .r ."  constant #FLAG" cr ;

\ re-derive keystream, decrypt BUF in place, and confirm it matches the plaintext
: self-check ( -- )
  derive  BUF #flag @ chacha20-xor
  BUF #flag @ PT #flag @ compare
  abort" author.fs: round-trip mismatch (flag/coloring/chacha broken)" ;

: main ( -- )
  read-flag
  derive  BUF #flag @ chacha20-xor   \ encrypt in place
  emit-cipher
  self-check ;
main
bye
