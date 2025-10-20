#!/bin/bash

latest_matching_filename() {
  FILES=($1)
  printf "%s\n" "${FILES[@]}" | sort --reverse | head -1
}
