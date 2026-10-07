# Cluster MPI Setup & Execution Guide (2 Nodes)

This guide documents the end-to-end configuration of an Open MPI distributed cluster over two Linux nodes (`victus` and `HP-Laptop`) on Ubuntu 24.04 LTS, including shared storage via NFS, key-based SSH authentication, and distributed job execution.

---

## 1. Environment & Prerequisites

* **Operating System:** Ubuntu 24.04 LTS on both machines
* **Compilers & Runtimes:** GCC 13.3.0, Open MPI 4.1.6
* **Cluster Nodes:**
  * Master node: `HP-Laptop`
  * Worker node: `victus`
* **Dedicated User:** `mpiuser` created on both machines with identical home paths (`/home/mpiuser`) to prevent path and permissions mismatch during remote execution.
* **Path**: `~/sod/nfs-cloud` on both machines

---

## 2. Software Installation

Installed the necessary toolchain and Open MPI libraries on both machines:

```bash
sudo apt update
sudo apt install build-essential libopenmpi-dev openmpi-bin openssh-server -y
```

---

## 3. Dedicated User Configuration

To ensure seamless path resolution and identical execution environments:

```bash
sudo adduser mpiuser
sudo usermod -aG sudo mpiuser
```

Logged in as `mpiuser` on both machines using the GUI.

---

## 4. Network & Hostname Resolution

1. Retrieved the local IP addresses of both machines on the local network interface:
   ```bash
   hostname -I
   ```
2. Configured static name resolution on **both** machines by editing `/etc/hosts`:
   ```bash
   sudo nano /etc/hosts
   ```
3. On `HP-Laptop`:
   ```text
   <IP_OF_VICTUS>     victus
   ```
4. On `victus`:
   ```text
   <IP_OF_HP_LAPTOP>  HP-Laptop
   ```
5. Verified reciprocal reachability:
   ```bash
   ping HP-Laptop   # executed on victus
   ping victus      # executed on HP-Laptop
   ```

---

## 5. Passwordless SSH Authentication

Open MPI relies on non-interactive SSH to spawn remote daemons (`orted`) across cluster nodes.

1. Generated an SSH key pair on the (`victus`) under `mpiuser` and accepted all the defaults:
   ```bash
   ssh-keygen -t ed25519
   ```
2. Copied the keys to (`HP-Laptop`):
   ```bash
   scp -r . mpiuser@HP-Laptop:.ssh
   ```
3. Verified that SSH connects without prompting for a password:
    * On `victus`
    ```bash
     ssh HP-Laptop
    ```
    * On `HP-Laptop`
    ```bash
     ssh victus
    ```

---

## 6. Shared Storage Setup (NFS) & Boot Optimization

To avoid manually copying files between machines across build cycles, a shared directory was configured via NFS:

* **Mount Path:** `/home/mpiuser/sod/nfs-cloud`
* `HP-Laptop` acts as the NFS server, exporting the directory.
* `victus` acts as the NFS client, mounting the export at the identical absolute path so that binaries compiled inside the folder are instantly available across both nodes.

### Server setup

1. Run on `HP-Laptop`:
    ```bash
    sudo apt-get install nfs-kernel-server
    ```
2. Added the following in `/etc/exports` at the end of the file: 
    ```text
    /home/mpiuser/sod/nfs-cloud *(rw,sync,no_subtree_check,no_root_squash)
    ```
3. To apply the changes:
    ```bash
     sudo exportfs -a
     ```

### Persistent Mount with Boot Hang Prevention (`/etc/fstab`)

When configuring persistent NFS mounts in `/etc/fstab`, standard entries cause systemd to stall boot by **1 minute 30 seconds** waiting for the remote share if `HP-Laptop` is offline or not on the same local network.

To resolve this boot delay on `victus`, systemd automount options with a low timeout were configured:

1. Edited `/etc/fstab` on `victus`:
   ```bash
   sudo nano /etc/fstab
   ```
2. Added the following entry:
   ```text
   #MPI CLUSTER SETUP
   HP-Laptop:/home/mpiuser/sod/nfs-cloud /home/mpiuser/sod/nfs-cloud nfs _netdev,nofail,noauto,x-systemd.automount,x-systemd.mount-timeout=5 0 0
   ```

**Option Breakdown:**
* `_netdev`: Delays mounting until the network stack is up.
* `nofail`: Prevents boot failure if the share cannot be reached.
* `noauto,x-systemd.automount`: Defers the physical mount until the folder is actively accessed instead of at system boot.
* `x-systemd.mount-timeout=5`: Limits the connection timeout to 5 seconds instead of the default 90-second hang if `HP-Laptop` is unavailable.

---

## 7. MPI Test Program & Compilation

Tested the laboratory [hello.c](`ex1b_helloworld.c`) and [hello-send-recv.c](ex2_helloworld_send+recv.c) inside the shared directory:

Compiled using the Open MPI wrapper `mpicc`:
```bash
cd ~/sod/nfs-cloud/mpi-setup-test
```

```bash
# first example
mpicc -Wall hello.c -o hello
mpirun --tag-output --host HP-Laptop:4,victus:8 hello 
# [1,5]<stdout>:[PID:12859] Hello World! From process 5 of 12 on victus.
# [1,7]<stdout>:[PID:12864] Hello World! From process 7 of 12 on victus.
# [1,0]<stdout>:[PID:12850] Hello World! From process 0 of 12 on victus.
# [1,1]<stdout>:[PID:12851] Hello World! From process 1 of 12 on victus.
# [1,2]<stdout>:[PID:12852] Hello World! From process 2 of 12 on victus.
# [1,3]<stdout>:[PID:12854] Hello World! From process 3 of 12 on victus.
# [1,4]<stdout>:[PID:12857] Hello World! From process 4 of 12 on victus.
# [1,6]<stdout>:[PID:12861] Hello World! From process 6 of 12 on victus.
# [1,9]<stdout>:[PID:11903] Hello World! From process 9 of 12 on HP-Laptop.
# [1,10]<stdout>:[PID:11904] Hello World! From process 10 of 12 on HP-Laptop.
# [1,11]<stdout>:[PID:11905] Hello World! From process 11 of 12 on HP-Laptop.
# [1,8]<stdout>:[PID:11902] Hello World! From process 8 of 12 on HP-Laptop.
```

```bash
# second example
mpicc -Wall hello-send-recv.c -o hello-sr
mpirun --tag-output --host HP-Laptop:4,victus:8 hello-sr 
# [1,0]<stdout>:[Task 0] Hello world, from process 0 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 1 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 2 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 3 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 4 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 5 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 6 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 7 of 12 on victus !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 8 of 12 on HP-Laptop !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 9 of 12 on HP-Laptop !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 10 of 12 on HP-Laptop !
# [1,0]<stdout>:[Task 0] I received the message: Hello world, from process 11 of 12 on HP-Laptop !
```

---

## 8. Known warnings

Ran the distributed MPI job across both hosts (5 processes on `victus`, 2 processes on `HP-Laptop`):

```bash
mpirun --tag-output --host victus:5,HP-Laptop:2 ./hello
```

### Note on Desktop Display Warnings
When running `mpirun` under a switched user session (`sudo su mpiuser`) on systems with active Wayland/X11 desktop managers, HWLOC/GPU hardware probing may emit non-fatal authorization warnings to `stderr`:
```text
Authorization required, but no authorization protocol specified
```
These warnings are strictly related to the local graphical server probing and do not affect MPI communication, computation, or memory management. Clean execution output can be isolated via:
```bash
mpirun --tag-output --host victus:5,HP-Laptop:2 ./hello 2>/dev/null
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
