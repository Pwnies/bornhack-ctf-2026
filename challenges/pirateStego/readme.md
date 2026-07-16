# Pirate Stego

## Description
```
Yarr! I found this treasure map in a bottle on the beach!
I think it from those yarrrrr 1 bit pirates! 
```

## Handout
handout.zip

## Flag
BHCTF{R3AL_T4eAs8re_W1s_t7e_fr1ends_w3_m2de}

## Walkthrough/Solution
Do 1 bit LSB,
Get Python script -> fix python script to get next image
Decode base64 from exif
From hint in image found in exif do LSB on the original image with the mask
R bit 5 → G bit 4 → R bit 6 → B bit 5 → G bit 2 → B bit 3

## How-to-run (Dynamic Challenges only)
N/A
