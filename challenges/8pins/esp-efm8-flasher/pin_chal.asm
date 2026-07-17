.area CODE

.include "efm8bb51.inc"

start:
    DISABLE_WATCHDOG

    ; P0 = digital
    mov P0MDIN, #0xff

    ; P0 = push-pull output
    mov P0MDOUT, #0xff

    ; P0 = all pins low
    mov P0, #0x00

    ; XBR2.XBARE = 1, enable output pins (crossbar stuff)
    orl XBR2, #0x40

outer:
    mov A, #0xFF
    acall delay

    ; letter index
    mov DPTR, #flag
loop:
    clr A
    movc A, @A+DPTR
    mov P0, A

    inc DPTR

    jz outer

    mov A, #0x02
    acall delay

    sjmp loop

delay:
    mov r7, A
d1:
    mov r6, #0xff
d2:
    djnz r6, d2
    djnz r7, d1

    ret

flag:
    .ascii "BHCTF{look_ma_teh_pins_are_wigglin}"
    .db 0
