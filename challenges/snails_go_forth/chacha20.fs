create cc-state 16 cells allot
create cc-work  16 cells allot
create cc-ks    64 allot
variable cc-idx
variable cc-ctr

: cc-m32 $FFFFFFFF and ;
: cc-rotl {: x n :} x n lshift  x 32 n - rshift or  cc-m32 ;
: cc-le@
  dup c@  over 1+ c@ 8 lshift or
  over 2 + c@ 16 lshift or  swap 3 + c@ 24 lshift or ;
: cc-x@ cells cc-work + @ ;
: cc-x! cells cc-work + ! ;

: cc-qr {: a b c d :}
  a cc-x@ b cc-x@ + cc-m32 a cc-x!   d cc-x@ a cc-x@ xor 16 cc-rotl d cc-x!
  c cc-x@ d cc-x@ + cc-m32 c cc-x!   b cc-x@ c cc-x@ xor 12 cc-rotl b cc-x!
  a cc-x@ b cc-x@ + cc-m32 a cc-x!   d cc-x@ a cc-x@ xor  8 cc-rotl d cc-x!
  c cc-x@ d cc-x@ + cc-m32 c cc-x!   b cc-x@ c cc-x@ xor  7 cc-rotl b cc-x! ;

: cc-block
  16 0 do i cells cc-state + @ i cells cc-work + ! loop
  10 0 do
    0 4  8 12 cc-qr   1 5  9 13 cc-qr   2 6 10 14 cc-qr   3 7 11 15 cc-qr
    0 5 10 15 cc-qr   1 6 11 12 cc-qr   2 7  8 13 cc-qr   3 4  9 14 cc-qr
  loop
  16 0 do i cc-x@ i cells cc-state + @ + cc-m32 i cells cc-work + ! loop
  16 0 do
    i 4 *  i cc-x@
    4 0 do dup $FF and  2 pick i + cc-ks + c!  8 rshift loop 2drop
  loop ;

: chacha20-init
  cc-ctr !
  $61707865 0 cells cc-state + !  $3320646e 1 cells cc-state + !
  $79622d32 2 cells cc-state + !  $6b206574 3 cells cc-state + !
  swap  8 0 do dup i 4 * + cc-le@  4 i + cells cc-state + ! loop drop
  3 0 do dup i 4 * + cc-le@  13 i + cells cc-state + ! loop drop
  64 cc-idx ! ;

: chacha20-xor
  over + swap ?do
    cc-idx @ 63 > if
      cc-ctr @ 12 cells cc-state + !  cc-block  1 cc-ctr +!  0 cc-idx !
    then
    i c@ cc-ks cc-idx @ + c@ xor i c!
    1 cc-idx +!
  loop ;
