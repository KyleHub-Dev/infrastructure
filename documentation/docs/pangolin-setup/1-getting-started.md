---
title: Getting Started
sidebar_position: 2
tags:
  - LXC Container
  - Docker Installation
  - Pangolin Installation
  - System Preparation
---

## 1. LXC Container Creation

### 1.1 Container Specifications

Create a new LXC container in Proxmox with the following specifications:

**Basic Settings:**
- **Template**: Debian 13 (trixie) or latest stable (e.g., `debian-13-standard_13.1-1_amd64.tar.zst`)
- **Hostname**: `pangolin`
- **Unprivileged container**: No (Docker requires privileged)
- **Nesting**: Yes (enable in Options after creation)
- **Keyctl**: Yes (enable in Options after creation)
- **Password**: Enter and confirm a strong password. (Alternative: Use a SSH Key)

**Resources:**
- CPU: 2 cores
- RAM: 2048 MB (2 GB)
- Swap: 512 MB
- Disk: 16 GB

**Network:**
- **Bridge**: `vmbr1` (your private LAN, as configured in [OPNsense Setup](../opnsense-setup.mdx))
- **IPv4**: Static (e.g., `192.168.1.50/24`)
- **Gateway**: Your OPNsense LAN IP (e.g., `192.168.1.1`)
- **IPv6**: If not required, leave all IPv6-related fields empty.

**DNS:**
- **DNS Domain**: This is your local network's domain name (e.g., `home.arpa`, `yourdomain.local`). It's used for local name resolution within your network. If you don't have a local domain name, you can leave this field empty.
- **DNS Server**: This is the IP address of the DNS server(s) the container will use. If you're using OPNsense as your DNS, enter its IP here (e.g., `192.168.1.1`).

### 1.2 Container Configuration for Docker

After creating the container, but **before starting it**, edit the container configuration to enable Docker support:

```bash
# On Proxmox host, edit the container config (replace <CTID> with your container ID)
nano /etc/pve/lxc/<CTID>.conf
```

Add these lines to enable Docker support:

```
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
```

Save the file (`Ctrl + O`, `Enter`, `Ctrl + X`) and start the container.

<details>
  <summary>Example LXC Container Configuration</summary>

```
arch: amd64
cores: 2
hostname: pangolin
memory: 2048
nameserver: 192.168.1.1
net0: name=eth0,bridge=vmbr1,firewall=1,gw=192.168.1.1,hwaddr=BC:24:11:03:8E:BE,ip=192.168.1.50/24,type=veth
ostype: debian
rootfs: local:200/vm-200-disk-0.raw,size=16G
swap: 512
lxc.apparmor.profile: unconfined
lxc.cgroup2.devices.allow: a
lxc.cap.drop:
lxc.mount.auto: proc:rw sys:rw
```
</details>

## 2. System Preparation

Once the container is started, you can access it via the Proxmox web interface console or SSH. Log in as the `root` user with the password you set during the container creation.

### 2.1 Update System

Enter the container console (via Proxmox web interface or SSH) and update the system:

```bash
# Update package lists and upgrade existing packages
apt update && apt upgrade -y
```

```bash
# Install basic utilities
apt install -y curl sudo git ca-certificates gnupg
```

### 2.2 Install Docker and Docker Compose

Install Docker using the official installation script:

```bash
# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

Expected output should show Docker version 20.x or higher and Docker Compose version 2.x or higher. 

## 3. Pangolin Installation

### 3.1 Quick Install (Recommended)

:::info Official Quick Install Documentation
This quick install method is largely based on the official Pangolin documentation available at [https://docs.digpangolin.com/self-host/quick-install](https://docs.digpangolin.com/self-host/quick-install).
:::

Pangolin provides a quick installation script that automates the setup process:

#### 3.1.1 Download & Run the Installer

```bash
# Run the quick install script
curl -fsSL https://digpangolin.com/get-installer.sh | bash
sudo ./installer
```

#### 3.1.2 Configure Basic Settings

The installer will prompt you for several basic settings:

- **Cloud Managed**: Do you want to install Pangolin as a cloud-managed (beta) node? (yes/no): **My recommendation**: **`no`**
- **Base Domain**: Enter your root domain without subdomains (e.g., `yourdomain.com`). *My example: `kylehub.dev` (you should use your own base domain)*
- **Dashboard Domain**: Press Enter to accept the default `pangolin.yourdomain.com` or enter a custom domain (e.g., `pangolin.kylehub.dev`). **My recommendation**: Press **`Enter`**
- **Let’s Encrypt Email**: Provide an email for SSL certificates and admin login. *My example: `admin@kylehub.dev` (replace with your actual email address)*
- Do you want to use Gerbil to allow tunneled connections (yes/no) (default: yes): **My recommendation**: Press Enter (accept default **`yes`**)
- Is your server IPv6 capable? (yes/no) (default: yes): **My recommendation**: Press Enter (accept default **`yes`**, but this can also be disabled)
- Would you like to run Pangolin as Docker or Podman containers? (default: docker): **My recommendation**: Press Enter (accept default **`docker`**)

#### 3.1.3 Configure Email

:::info
Email functionality is optional and can be added later.
:::

Choose whether to enable SMTP email functionality:
*   **Default**: No (recommended for initial setup)
*   If enabled: You’ll need SMTP server details (host, port, username, password)

**My recommendation**: Select **`No`** for email functionality during initial setup.

#### 3.1.4 Start Installation

Confirm that you want to install and start the containers:
*   The installer will pull Docker images (pangolin, gerbil, traefik)
*   Containers will be started automatically
*   This process takes 2-3 minutes depending on your internet connection
*   You’ll see progress indicators as each container is pulled and started.

**My recommendation**: Proceed with the installation by selecting **`Yes`.**

#### 3.1.5 Install CrowdSec (Optional)

The installer will ask if you want to install CrowdSec for additional security:
*   **Default**: No (**recommended for initial setup**)
*   If enabled: You’ll need to confirm you’re willing to manage CrowdSec configuration

:::warning
CrowdSec adds complexity and requires manual configuration for optimal security. Only enable if you’re comfortable managing it.
:::
:::info
CrowdSec can be installed later if needed. The basic installation provides sufficient security for most use cases.
:::

**My recommendation**: Skip CrowdSec for now by selecting **`No`.**

#### 3.1.6 Initial Access & Setup Token

Once the installation is complete, the installer will display a **Setup Token**. You must copy and save this token immediately, as it is required for the initial setup of Pangolin.
