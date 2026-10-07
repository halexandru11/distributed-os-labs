# Cluster MPI Setup & Execution Guide (2 Nodes)

This guide documents the end-to-end configuration of an Open MPI distributed cluster over two Linux nodes (`victus` and `HP-Laptop`) on Ubuntu 24.04 LTS, including shared storage via NFS, key-based SSH authentication, and distributed job execution.

---

## 1. Environment & Prerequisites

* **Operating System:** Ubuntu 24.04 LTS on both machines
* **Compilers & Runtimes:** GCC 13, Open MPI 4.1.6
* **Cluster Nodes:**
  * Master node: `victus`
  * Worker node: `HP-Laptop`
* **Dedicated User:** `mpiuser` created on both machines with identical UID, GID, and home paths (`/home/mpiuser`) to prevent path and permissions mismatch during remote execution.

---

## 2. Software Installation

Installed the necessary toolchain and Open MPI libraries on both machines:

```bash
sudo apt update
sudo apt install build-essential libopenmpi-dev openmpi-bin openssh-server -y
sudo systemctl enable --now ssh
```

---

## 3. Dedicated User Configuration

To ensure seamless path resolution and identical execution environments:

```bash
sudo adduser mpiuser
sudo usermod -aG sudo mpiuser
```

Logged in as `mpiuser` on both machines:
```bash
su - mpiuser
```

---

## 4. Network & Hostname Resolution

1. Retrieved the local IP addresses of both machines on the local network interface:
   ```bash
   ip -4 a
   ```
2. Configured static name resolution on **both** machines by editing `/etc/hosts`:
   ```bash
   sudo nano /etc/hosts
   ```
   Added entries for both nodes:
   ```text
   <IP_OF_VICTUS>     victus
   <IP_OF_HP_LAPTOP>  HP-Laptop
   ```
3. Verified reciprocal reachability:
   ```bash
   ping -c 2 HP-Laptop   # executed on victus
   ping -c 2 victus      # executed on HP-Laptop
   ```

---

## 5. Passwordless SSH Authentication

Open MPI relies on non-interactive SSH to spawn remote daemons (`orted`) across cluster nodes.

1. Generated an SSH key pair on the master node (`victus`) under `mpiuser`:
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
   ```
2. Copied the public key to the worker node (`HP-Laptop`):
   ```bash
   ssh-copy-id mpiuser@HP-Laptop
   ```
3. Verified that SSH connects without prompting for a password:
   ```bash
   ssh HP-Laptop "hostname"
   ```

---

## 6. Shared Storage Setup (NFS)

To avoid manually copying binaries between machines across build cycles, a shared directory was configured via NFS:

* **Mount Path:** `/home/mpiuser/sod/nfs-cloud/test`
* The master node exports the folder, and the worker node mounts it at the exact same absolute path.
* This ensures that binaries compiled on `victus` are instantaneously available to `HP-Laptop`.

---

## 7. MPI Test Program & Compilation

Created a test application (`hello.c`) inside the shared directory:

```c
#include <mpi.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    int world_size, world_rank;
    char hostname[256];

    MPI_Comm_size(MPI_COMM_WORLD, &world_size);
    MPI_Comm_rank(MPI_COMM_WORLD, &world_rank);
    gethostname(hostname, sizeof(hostname));

    printf("Hello World! From process %d of %d on %s.\n", world_rank, world_size, hostname);

    MPI_Finalize();
    return 0;
}
```

Compiled using the Open MPI wrapper `mpicc`:
```bash
cd ~/sod/nfs-cloud/test
mpicc hello.c -o hello
```

---

## 8. Distributed Execution & Verification

Ran the distributed MPI job across both hosts (5 processes on `victus`, 2 processes on `HP-Laptop`):

```bash
mpirun --tag-output --host victus:5,HP-Laptop:2 ./hello
```

### Note on Desktop Display Warnings
When running `mpirun` under a switched user session (`su - mpiuser`) on systems with active Wayland/X11 desktop managers, HWLOC/GPU hardware probing may emit non-fatal authorization warnings to `stderr`:
```text
Authorization required, but no authorization protocol specified
```
These warnings are strictly related to the local graphical server probing and do not affect MPI communication, computation, or memory management. Clean execution output can be isolated via:
```bash
env -u DISPLAY -u XAUTHORITY mpirun --tag-output --host victus:5,HP-Laptop:2 ./hello 2>/dev/null
```

### Successful Output
```text
[1,0]<stdout>: Hello World! From process 0 of 7 on victus.
[1,1]<stdout>: Hello World! From process 1 of 7 on victus.
[1,2]<stdout>: Hello World! From process 2 of 7 on victus.
[1,3]<stdout>: Hello World! From process 3 of 7 on victus.
[1,4]<stdout>: Hello World! From process 4 of 7 on victus.
[1,5]<stdout>: Hello World! From process 5 of 7 on HP-Laptop.
[1,6]<stdout>: Hello World! From process 6 of 7 on HP-Laptop.
```