---
title: Prerequisites
sidebar_position: 1
---

:::danger Disclaimer

This documentation is a guide detailing the steps I took to set up my own personal environment. While it is intended to be a helpful resource, it is not an official or professionally endorsed guide. You should have a good understanding of the technologies and procedures involved before attempting to replicate this setup.

The information is provided "as is" without any representations or warranties, express or implied. Any reliance you place on this guide is strictly at your own risk.

In no event will I be liable for any loss or damage, including without limitation, indirect or consequential loss or damage, or any loss or damage whatsoever arising from loss of data or profits arising out of, or in connection with, the use of this documentation.

:::

This document outlines the prerequisites for setting up the Personal Enterprise Platform.

## Required Accounts and Services

To follow this guide, you will need the following accounts and services:

*   **Cloudflare Account**: For domain management and DNS services.
*   **Domain**: A registered domain, preferably managed through Cloudflare. (e.g., kylehub.dev)
*   **Hetzner Account**: To provision a dedicated server.
*   **Hetzner Server (e.g., AX41-NVMe)**: A dedicated server from Hetzner.
*   **Additional IP Address (Hetzner)**: Essential for obtaining a separate MAC address, which will be needed later for OPNsense.

## Recommended Tools

These tools will greatly assist you during the setup process:

*   **Terminal Application**: To access and manage your servers (e.g., SSH client).
*   **Password Manager (e.g., KeePassXC)**: To securely store and manage your credentials.
*   **Browser (e.g., Brave)**: For accessing web interfaces and documentation.

## Operating System Installation

Before proceeding, ensure your Hetzner server has **Debian 13 Trixie** installed. If it's not already installed, you have two primary options:

### Option 1: Via Hetzner Robot (Recommended for initial setup)

1.  Log in to `robot.hetzner.com`.
2.  Navigate to your server.
3.  Under the "Linux" tab, select "Debian 13 base" and initiate the Linux installation.

### Option 2: Via Hetzner Rescue System

This method provides more flexibility and is useful if you need to re-install or customize.

1.  Boot your server into the [Hetzner Rescue System](https://docs.hetzner.com/de/robot/dedicated-server/troubleshooting/hetzner-rescue-system/).
2.  Once in rescue mode, log in via SSH and run the `installimage` command.
3.  Follow the prompts to select and install "Debian 13 (trixie)".
4.  Complete the installation process.

After Debian 13 Trixie is successfully installed, you can proceed with the Proxmox setup. For a detailed guide on installing and configuring Proxmox VE, refer to the official Hetzner tutorial: [Install and Configure Proxmox VE](https://community.hetzner.com/tutorials/install-and-configure-proxmox_ve/).