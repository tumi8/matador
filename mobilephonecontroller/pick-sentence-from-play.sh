#!/bin/bash

# picks a random line from a text file. We used "Death of a Salesman" lines, which we
# do not include here for copyright reasons. 

#file="death_of_a_salesman_sentences_postprocessed.txt"
file="sentences.txt"

lines=`wc -l $file| cut -d " " -f 1 `
word=""


rand=$[$RANDOM%$lines]
head -n $rand $file | tail -n 1

exit 0
