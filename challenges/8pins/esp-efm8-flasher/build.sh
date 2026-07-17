#!/bin/sh
rm pin_chal.ihx pin_chal.rel pin_chal.lst pin_chal.sym
sdas8051 -los pin_chal.asm
sdld -nui -b CODE=0 pin_chal.rel
