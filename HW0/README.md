# HW0 — Configurarea clusterului MPI

Tema pregătește două calculatoare, HP-Laptop și Victus, pentru execuție distribuită cu Open MPI, SSH și stocare comună NFS.

- [setup.md](setup.md): configurarea mediului și verificarea conexiunii.
- [hello.c](hello.c): afișarea rangului și a calculatorului fiecărui proces.
- [hello-send-recv.c](hello-send-recv.c): schimb de mesaje între procese.

Compilare și verificare locală, din directorul `HW0`:

```bash
mpicc -Wall hello.c -o hello
mpirun --oversubscribe -np 4 ./hello
mpicc -Wall hello-send-recv.c -o hello-sr
mpirun --oversubscribe -np 4 ./hello-sr
```

[Toate temele](../README.md)
