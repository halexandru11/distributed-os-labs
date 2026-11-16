CC = gcc
CFLAGS = -O3 -std=c11 -Wall -Wextra -Wpedantic
OMPFLAGS = -fopenmp

.PHONY: all test clean debug
all: matmul

matmul: matmul.c
	$(CC) $(CFLAGS) $(OMPFLAGS) $< -o $@

debug: matmul.c
	$(CC) -O1 -g -std=c11 -Wall -Wextra -Wpedantic $(OMPFLAGS) -fsanitize=undefined -fno-sanitize-recover=all $< -o matmul_debug

test: matmul
	python3 -m unittest discover -s tests -v

clean:
	rm -f matmul matmul_debug
