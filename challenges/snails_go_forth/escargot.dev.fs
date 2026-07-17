require ./chacha20.fs
1 cells 8 = 0= [if] cr ." The Great Escargot needs a 64-bit gforth. Aborting." cr bye [then]

create CIPHER
  149 c,
  188 c,
  169 c,
  166 c,
  250 c,
  134 c,
  132 c,
  252 c,
  121 c,
  244 c,
  120 c,
   65 c,
  226 c,
  227 c,
  226 c,
   46 c,
  223 c,
  238 c,
  107 c,
   89 c,
  209 c,
  166 c,
   78 c,
   93 c,
   64 c,
  228 c,
  233 c,
  191 c,
    1 c,
  143 c,
    5 c,
  233 c,
  158 c,
  107 c,
   31 c,
  109 c,
  122 c,
  212 c,
38 constant #FLAG
create OUTBUF 48 allot

create OWNER  36 allot
create WALL   36 allot
create PA      5 cells allot
create HA      5 cells allot
create TA      5 cells allot
create FA      5 cells allot
variable CUR   variable CENSUS  variable MOVES
variable TGT   variable DIRV
create LBUF 200 allot
variable IA  variable INN

: snail-name
  case 1 of ." Gary"  endof  2 of ." Turbo" endof
       3 of ." Pearl" endof  4 of ." Brian" endof endcase ;
: dir.
  DIRV @ case 1 of ." up"   endof  2 of ." down"  endof
              3 of ." left" endof  4 of ." right" endof endcase ;

: describe
  case
     1 of ." Cold gravel of the hard standing. The bucket's smell is still on you." endof
     2 of ." Cool soil in the bucket's shadow. Behind you, the blue dome you poured out of. Ahead: the whole green night." endof
     4 of ." A gap in the wall opens into a little room the bricks forgot — and up" cr
           ." high, turning slowly, a glint: a tiny mirrored ball, catching the" cr
           ." security light and flinging a hundred spinning stars across the dark." cr
           ." Somewhere a beat kicks in. You don't decide to dance. You just... do." cr
           ." It turns out every snail shell has a tiny mirror-ball of its own, and" cr
           ." yours has been waiting all its life for this. For one whole glorious" cr
           ." minute there's no bucket, no gardener, no supper — only you, the groove," cr
           ." and a silver trail shining like it's finally going somewhere." cr
           ." Then the light steadies, the beat fades, and it's a quiet corner again." cr
           ." (You are, it must be said, now stuck in a corner. Worth it.)" endof
     7 of ." Trodden earth. A wall breathes cold somewhere close; the good green dark is everywhere else." endof
     9 of ." Soft mulch between the beds. Your foot sinks in without a sound." endof
    10 of ." Peppery air, electric — you can practically taste fast from here. Let's MOVE." endof
    11 of ." The edge of things — cold glass one side, colder water the other. A fine place to think. You consider the water. You reconsider immediately." endof
    12 of ." Damp, dark leaf-mould in the corner. You check your whorl in a dewdrop. Presentable. For one glorious second, supper is forgotten." endof
    13 of ." Rich dug earth. The good green smell gets stronger the lower you go." endof
    14 of ." A worm surfaces and delivers its one and only joke: what do you call a snail on a ship? A SNAILOR! It is gone before you can groan. You will think about this all night." endof
    15 of ." Cold flower stems, petals shut for the night. Nothing here you'd want to eat." endof
    16 of ." Butterhead lettuce — wonderful, but not what you came for. Not yours. Keep crawling." endof
    17 of ." Reeds hiss. The pond breathes cold at your side. Keep to the good earth. You consider the water. You reconsider immediately." endof
    18 of ." Soft mould underfoot, the west wall cold beside you, the compost sighing somewhere near. For one glorious second, supper is forgotten." endof
    19 of ." Bare crumbly soil. It takes your trail cleanly." endof
    21 of ." Netting droops overhead, strung against the birds. A sweet red smell drifts through it." endof
    22 of ." Warm mulch, and a green pepperiness rising. Something you'd like is close." endof
    23 of ." A ladybird is sunbathing here. It is the middle of the night. You decide it isn't your place to say anything." endof
    24 of ." The dry-stone wall turns the corner here — cold mossy flint, fitted tight. No gap for a snail." endof
    25 of ." Cool dug earth in the wall's shadow." endof
    26 of ." Cabbage-cool air, thick and green. Very close now." endof
    27 of ." The Great Cabbage — wonderful, but not what you came for. Not yours. Keep crawling." endof
    28 of ." The rocket — wonderful, but not what you came for. Not yours. Keep crawling." endof
    29 of ." A strawberry — wonderful, but not what you came for. Not yours. Keep crawling." endof
    30 of ." Along the foot of the long wall. Cold stone above, cold earth below." endof
    31 of ." Gravel and grit at the wall's foot. Every inch a small argument." endof
    32 of ." The wall's shadow runs on. Damp, quiet, endless." endof
    33 of ." Cool soil, well trodden. The dark smells faintly of everything at once." endof
    34 of ." The last of the beds along the wall. A sweet red smell, very near now." endof
    35 of ." The far corner, dry-stone wall on two sides. A dead end for anyone but a snail with a plan. A painted gnome stands guard beyond the wall, forever, over nothing. The gnome knows what you did. The gnome will never tell." endof
  endcase cr ;

: obstacle.
  case
     0 of ." the greenhouse's cold glass corner" endof
     3 of ." the rockery — a tumble of sharp flint" endof
     5 of ." the greenhouse wall" endof
     6 of ." the dry-stone wall" endof
     8 of ." the Boot — a fallen wellington, huge and cracked" endof
    20 of ." the upturned wheelbarrow" endof
  endcase ;

: move-line
  CUR @ case
    1 of ." You crawl "   dir. ." . No fuss. One trail, straight and true." endof
    2 of ." You BLAST "   dir. ." . (One tile. It felt like nine.)" endof
    3 of ." You glide "   dir. ." , whorl to the light. A lady does not hurry." endof
    4 of ." You proceed " dir. ." , arriving a little more slowly at where you already were." endof
  endcase cr ;

: blocked-edge
  ." You nose " dir. ."  and meet the garden's edge — cold stone. No way through." cr ;

: blocked-wall
  CUR @ case
    2 of ." You hit " TGT @ obstacle. ."  at full speed. It wins. It always wins." endof
    3 of ." You will not scuff your shell on " TGT @ obstacle. ." ." endof
    4 of TGT @ obstacle. ." . You contemplate it a while. It remains " TGT @ obstacle. ." ." endof
    1 of ." You nose " dir. ."  and meet " TGT @ obstacle. ." . Best not." endof
  endcase cr ;

: home-status
  CENSUS @ 3 = if ." Home: 3 of 4 — one supper to go." cr
  else ." Home: " CENSUS @ 0 .r ."  of 4." cr then ;

: arrival
  CUR @ case
    1 of ." A cabbage the size of a cathedral. You press your whole face to it and weep one small, happy tear." endof
    2 of ." Peppery green fireworks! You do a lap of honour. It takes nine minutes." cr
          ." You insist you got there first. You got there last. Nobody argues." endof
    3 of ." A strawberry blushing in the dusk. You pronounce it acceptable and devour it." endof
    4 of ." A leaf like folded silk. You settle in for a very long, very satisfying think." endof
  endcase cr ;

: inner-voice
  CUR @ case
    1 of ." (One trail, straight and true. You can do this.)" endof
    2 of ." (OH YES. Where were we. Fast. We were being fast.)" endof
    3 of ." (Is your whorl catching the light? ...not near a crossing, darling.)" endof
    4 of ." (There is no rush. There is only the trail.)" endof
  endcase cr ;

: intro-screen
  cr ."         🐌  THE GREAT ESCARGOT  🐌" cr cr
  ." The brick has slipped. The bucket's lip lifts a snail's-width," cr
  ." and you pour out into the cool blue dusk with the rest of the colony." cr cr
  ." Tonight you are a snail — four of you, really, and you can slip" cr
  ." from one shell into the next. Each of you has dreamed all week of" cr
  ." a different supper, somewhere out there in the dark." cr cr
  ." Find your way to it. But leave no crossing: where one silver trail" cr
  ." kisses another, the slime pools thick and winks in the torchlight," cr
  ." and Mr. Fothergill is out in his slippers with the jam jar." cr cr
  ."   Commands:  up  down  left  right  next  help" cr
  ."   ('next' slips you into the next snail. One shell at a time.)" cr cr
  ." The dew won't last till morning. Off you go." cr cr ;

: help-screen
  cr ."   up / down / left / right  — crawl one tile" cr
  ."   next                      — slip into the next snail" cr
  ."   help                      — this" cr
  ."   quit                      — give up for tonight" cr cr
  ." You can't see much — snails never do. You know the world by scent," cr
  ." by damp, by the tremble of the ground, and it comes to you on its own:" cr
  ." after every step, the tile beneath you tells you what it is." cr
  ." What Mr. Fothergill knows is a CROSSING: where two trails pool thick" cr
  ." and wink in the torchlight. Keep every trail apart." cr cr ;

: win-screen
  cr ." The last snail settles onto its supper. Four silver trails laid down," cr
  ." and not one has crossed another — the whole garden lies still and" cr
  ." silver and innocent under the moon." cr cr
  ." Mr. Fothergill sleeps. The colony feasts." cr cr
  ." Dawn. Four empty supper-beds. Mr. Fothergill stands in his slippers," cr
  ." staring at a garden with no snails, no crossings, and no explanation" cr
  ." at all. He never does work out how they did it." cr cr ;

: fail-screen
  cr ." Two silver threads touch — and pool thick, and wink," cr
  ." one bright tell-tale wink of crossed slime under the security light." cr cr
  ." A back door opens. Slippers on the gravel." cr
  ." '...out again, are we,' sighs Mr. Fothergill, not even cross." cr cr
  ." One gentle scoop at a time, the colony goes back in the bucket:" cr
  ." a fresh brick on the lid, a stern word none of you will heed," cr
  ." and — because he's soft, and can't help it — one lettuce leaf" cr
  ." tucked in anyway." cr cr
  ."               Caught. Try again tomorrow night?  [y/n]" cr ;

: init-world
  OWNER 36 0 fill
  WALL  36 0 fill
  1 WALL  0 + c!  1 WALL  3 + c!  1 WALL  5 + c!
  1 WALL  6 + c!  1 WALL  8 + c!  1 WALL 20 + c!
   2 1 cells TA + !   27 1 cells FA + !
  10 2 cells TA + !   28 2 cells FA + !
  12 3 cells TA + !   29 3 cells FA + !
  11 4 cells TA + !   16 4 cells FA + !
  5 1 do
    i cells TA + @  i cells PA + !
    0 i cells HA + !
    i  i cells TA + @ OWNER + c!
  loop
  0 CENSUS !  0 MOVES !  1 CUR ! ;

: do-quit
  cr ." The colony creeps back to the bucket of its own accord. Goodnight." cr
  bye ;

: do-win
  win-screen
  ."         🥬  "
  OWNER  OWNER 24 +  0 chacha20-init
  CIPHER OUTBUF #FLAG move
  OUTBUF #FLAG chacha20-xor
  OUTBUF #FLAG type
  ."   🥬" cr cr
  bye ;

: step
  DIRV @ case
    1 of dup 6 /   0> if 6 - true else drop -1 false then endof
    2 of dup 6 /   5 < if 6 + true else drop -1 false then endof
    3 of dup 6 mod 0> if 1 - true else drop -1 false then endof
    4 of dup 6 mod 5 < if 1 + true else drop -1 false then endof
  endcase ;

: reset-world
  init-world
  cr ." The dew is still wet. You pour out of the bucket again, and begin." cr cr
  CUR @ cells PA + @ describe ;

: get-line
  stdin isatty if
    LBUF 190 accept
  else
    LBUF 190 stdin read-line throw 0= if do-quit then
  then ;

: read-token
  get-line
  cr LBUF swap
  INN ! IA !
  begin INN @ 0> IA @ c@ bl = and while 1 IA +! -1 INN +! repeat
  IA @ 0
  begin INN @ 0> IA @ c@ bl <> and while 1+ 1 IA +! -1 INN +! repeat ;

: do-fail
  fail-screen
  read-token
  2dup s" n"  compare 0= >r
  2dup s" no" compare 0= r> or if 2drop do-quit then
  2drop reset-world ;

: do-move
  CUR @ cells HA + @ if drop
    ." You are home, curled happily on your supper — you couldn't be moved for the world. (Try next.)" cr exit then
  DIRV !
  CUR @ cells PA + @ step
  0= if drop blocked-edge exit then
  TGT !
  TGT @ WALL + c@ if blocked-wall exit then
  TGT @ OWNER + c@ if do-fail exit then
  1 MOVES +!
  CUR @ TGT @ OWNER + c!
  TGT @ CUR @ cells PA + !
  move-line
  TGT @ CUR @ cells FA + @ = if
    arrival  true CUR @ cells HA + !  1 CENSUS +!  home-status
    CENSUS @ 4 = if do-win then
  else TGT @ describe then ;

: unhomed# 0  5 1 do i cells HA + @ 0= if 1+ then loop ;

: pov-switch
  unhomed# 1 = if 2drop ." Only you left now. No pressure." cr
  else
    ." You let go of " swap snail-name
    ."  and wake in " snail-name
    ."  — a new shell, a new set of nerves." cr
  then
  inner-voice
  CUR @ cells PA + @ describe ;

: do-next
  CUR @
  CUR @
  begin 1+ dup 4 > if drop 1 then dup cells HA + @ 0= until
  CUR !
  CUR @ pov-switch ;

: unknown
  ." Snails don't know that word. Try: up, down, left, right, next, help." cr ;

: dispatch
  2dup s" up"    compare 0= if 2drop 1 do-move exit then
  2dup s" down"  compare 0= if 2drop 2 do-move exit then
  2dup s" left"  compare 0= if 2drop 3 do-move exit then
  2dup s" right" compare 0= if 2drop 4 do-move exit then
  2dup s" next"  compare 0= if 2drop do-next exit then
  2dup s" help"  compare 0= if 2drop help-screen exit then
  2dup s" quit"  compare 0= if 2drop do-quit exit then
  dup 0= if 2drop exit then
  2drop unknown ;

: repl
  begin CUR @ snail-name ."  › " read-token dispatch again ;

: run
  init-world
  intro-screen
  CUR @ cells PA + @ describe
  repl ;

run
bye
