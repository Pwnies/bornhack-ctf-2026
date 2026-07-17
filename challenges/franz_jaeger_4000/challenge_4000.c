#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void rev(char* str) { 
    int l, i; 
    char *begin_ptr, *end_ptr, ch; 
  
    // Get the length of the string 
    l = strlen(str); 
  
    // Set the begin_ptr and end_ptr 
    // initially to start of string 
    begin_ptr = str; 
    end_ptr = str; 
  
    // Move the end_ptr to the last character 
    for (i = 0; i < l - 1; i++) 
        end_ptr++; 
  
    // Swap the char from start and end 
    // index using begin_ptr and end_ptr 
    for (i = 0; i < l / 2; i++) { 
  
        // swap character 
        ch = *end_ptr; 
        *end_ptr = *begin_ptr; 
        *begin_ptr = ch; 
  
        // update pointers positions 
        begin_ptr++; 
        end_ptr--; 
    } 
}




int pin3_0(int x) {
    return (x+0x17);
}

int pin3_1(int x) {
    return (x-0x0e);
}

int pin3_2(int x) {
    return (x*0x04);
}

int pin3_3(int x) {
    return (x*0x0d*0x02);
}


void alarm_1() {
    printf("## Ohh no! You triggered the first alarm! ##\n");
    printf("## Are you sure you know what you're doing? ##\n");
    exit(1);
}



void alarm_2() {
    printf("## You triggered the second alarm! ##\n");
    printf("## The police are on the way! ##\n");
    exit(1);
}


void alarm_3() {
    printf("## You triggered the third alarm! ##\n");
    printf("## Detective Holm & Jensen are already in the building! ##\n");
    exit(1);
}


void alarm_4() {
    printf("## You triggered the fourth and final alarm! ##\n");
    printf("## Watch out! 'Bøffen' is right behind you! ##\n");
    exit(1);
}



int main() {

    // j3g_h4r_3n_pl4n!
    // !n4l p_n3 _r4h _g3j

    // Variables
    char total_input [16] = "";
    char user_input [6];
    int user_input_len = 0;


    printf("################################################\n");
    printf("##### Welcome to the FRANZ JÄGER 4000 safe #####\n");
    printf("################################################\n\n");
    printf("Please enter the correct pin codes,\nor an alarm will call the police!\n \n");


    // *** Pin 1 ***
    // !n4l
    printf("Input pin #1: ");
    scanf("%s", user_input);
    user_input_len = strlen(user_input);

    // Checks the 'string length'
    if (user_input_len != 4){
        alarm_1();
    }

    if (user_input[0] != '!'){
        alarm_1();
    }
    if (user_input[1] != 'n'){
        alarm_1();
    }
    if (user_input[2] != '4'){
        alarm_1();
    }
    if (user_input[3] != 'l'){
        alarm_1();
    }

    strcat(total_input, user_input);



    // *** Pin 2 ***
    // p_n3
    printf("Input pin #2: ");
    scanf("%s", user_input);
    user_input_len = strlen(user_input);

    // Checks the 'string length'
    if (user_input_len != 4){
        alarm_2();
    }

    if ((333/9)-34 != (user_input[3] - '0')){
        alarm_2();
    }
    if ((user_input[2] ^ 0x6e) != 0){
        alarm_2();
    }
    if ((user_input[1] ^ 0x5f) != 0){
        alarm_2();
    }
    if ((user_input[0] ^ 0x70) != 0){
        alarm_2();
    }

    strcat(total_input, user_input);



    // *** Pin 3 ***
    // _r4h
    printf("Input pin #3: ");
    scanf("%s", user_input);
    user_input_len = strlen(user_input);

    // Checks the 'string length'
    if (user_input_len != 4){
        alarm_3();
    }

    if ((user_input[0] ^ pin3_0(0x48)) != 0){
        alarm_3();
    }
    if ((user_input[1] ^ pin3_1(0x80)) != 0) {
        alarm_3();
    }
    if ((user_input[2] ^ pin3_2(0x0d)) != 0) {
        alarm_3();
    }
    if ((user_input[3] ^ pin3_3(0x04)) != 0) {
        alarm_3();
    }


    strcat(total_input, user_input);



    // *** Pin 4 ***
    // _g3j
    printf("Input pin #4: ");
    scanf("%s", user_input);
    user_input_len = strlen(user_input);

    // Checks the 'string length'
    if (user_input_len != 4){
        alarm_4();
    }

    // Check 1: Weighted sum constraint
    // 95*7 + 103*3 + 51*2 + 106*1 = 665 + 309 + 102 + 106 = 1182
    if ((user_input[0] * 7) + (user_input[1] * 3) + (user_input[2] * 2) + (user_input[3] * 1) != 1182){
        alarm_4();
    }

    // Check 2: Different weighted sum
    // 95*2 + 103*5 + 51*4 + 106*3 = 190 + 515 + 204 + 318 = 1227
    if ((user_input[0] * 2) + (user_input[1] * 5) + (user_input[2] * 4) + (user_input[3] * 3) != 1227){
        alarm_4();
    }

    // Check 3: Another weighted combination
    // 95*11 + 103*13 + 51*17 + 106*19 = 1045 + 1339 + 867 + 2014 = 5265
    if ((user_input[0] * 11) + (user_input[1] * 13) + (user_input[2] * 17) + (user_input[3] * 19) != 5265){
        alarm_4();
    }

    // Check 4: Subtraction-based constraint
    // 95*23 - 103*29 + 51*31 - 106*37 = 2185 - 2987 + 1581 - 3922 = -3143
    if ((user_input[0] * 23) - (user_input[1] * 29) + (user_input[2] * 31) - (user_input[3] * 37) != -3143){
        alarm_4();
    }


    strcat(total_input, user_input);

    printf("\n");
    printf("### The Franz Jäger safe slowly opens..!\n");
    printf("### But it's empty!\n");
    printf("### You're certain that the evil 'Bagmand' is behind this!\n");
    printf("### All you have is the pin you entered... Wait a minute, that's it!\n\n");

    // Prints the flag
    rev(total_input);
    printf("### BHCTF{%s}", total_input);
    printf("\n");
}