# Proton Mail Bridge & Local SMTP Relay Setup

This guide details how to set up a secure, headless email sending infrastructure using Proton Mail Bridge and Postfix.

## Important Usage Note: Production Use & Limits

You are using a Proton Mail Pro/Business plan, which offers significantly higher sending limits and custom domain support compared to free accounts. However, please note:

*   **Transactional vs. Bulk:** Proton Mail is optimized for secure business communication. While it can handle transactional emails (password resets, notifications) for standard business operations, it is not a dedicated bulk emailing service.
*   **Best Practice:** Ensure your sending volume remains consistent and avoids "spam-like" bursts. If your application scales to massive volumes (e.g., tens of thousands of emails daily), dedicated Transactional Email Service Providers (Postmark, SendGrid) are recommended to ensure deliverability and reputation management.
*   **Custom Domains:** This setup fully supports your custom domain (e.g., `noreply@yourdomain.com`). Ensure this address is configured as an alias in your Proton account.

---

## Architecture

To ensure reliability and compatibility, we use a 3-Tier Architecture:

1.  **Application (e.g., Zitadel):** Connects to `localhost:25` (standard, unencrypted). Simple and fast.
2.  **Middleware (Postfix):**
    *   Listens on `localhost:25` (and Docker network interface).
    *   Queues mail (prevents data loss if Bridge is busy).
    *   Translates simple traffic into the complex encrypted authentication required by the Bridge.
    *   **Authentication:** Accepts SASL authentication from local apps (like Zitadel) using a local Linux user.
3.  **Proton Mail Bridge:**
    *   Listens on `localhost:1025`.
    *   Encrypts mail and sends it to Proton servers.

```mermaid
graph LR
    A[Zitadel / Apps] -- SMTP (Auth: zitadel) --> B(Postfix Relay :25)
    B -- SMTP (Auth: proton + TLS) --> C(Proton Mail Bridge :1025)
    C -- Encrypted Tunnel --> D[Proton Mail Cloud]
```

---

## Phase 1: Headless Proton Mail Bridge Setup

Since we are on a headless Linux server, we cannot use the GUI. We must use `gpg` and `pass` to handle credentials securely.

### 1. Install Dependencies
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y pass gnupg
```

### 2. Download & Install Bridge
Download the latest `.deb` from the [Proton Bridge Release Page](https://proton.me/mail/bridge).
```bash
wget https://proton.me/download/bridge/protonmail-bridge_3.21.2-1_amd64.deb -O proton-bridge.deb
sudo dpkg -i proton-bridge.deb
rm proton-bridge.deb
```

### 3. Create Isolated Service User
We run the bridge as a restricted user (`proton`) for security.
```bash
# Create user with no login shell
sudo useradd -r -s /bin/false proton

# Create home and log directories
sudo mkdir -p /home/proton /var/log/proton-bridge
sudo chown -R proton:proton /home/proton /var/log/proton-bridge
```

### 4. Setup Key Store (GPG & Pass)
Execute these commands specifically as the `proton` user to initialize the headless keychain.

```bash
# Switch to proton user context temporarily
sudo -u proton bash

# 1. Generate GPG key (Leave passphrase EMPTY for headless auto-start)
gpg --batch --passphrase '' --quick-gen-key 'ProtonMail Bridge' default default never

# 2. Initialize pass database
pass init "ProtonMail Bridge"

# 3. Exit back to root/sudo user
exit
```

### 5. Login & Configure Bridge
Run the bridge CLI interactively **once** to login.

```bash
sudo -u proton protonmail-bridge --cli
```

**Inside the CLI:**
1.  Type `login`.
2.  Enter your Proton Mail username (e.g., `admin@yourdomain.com`) and password.
3.  Type `info` to see your configuration.
4.  **IMPORTANT:** Note down the **SMTP Username** (usually your email) and **SMTP Password** (a generated string, *not* your login password). You will need these for Postfix.
5.  Type `exit`.

### 6. Daemonize (Systemd Service)
Create a service to keep the bridge running.

`sudo nano /etc/systemd/system/proton-bridge.service`

```ini
[Unit]
Description=ProtonMail Bridge
After=network.target

[Service]
Type=simple
User=proton
ExecStart=/usr/bin/protonmail-bridge --noninteractive
StandardOutput=append:/var/log/proton-bridge/bridge.log
StandardError=append:/var/log/proton-bridge/error.log
Restart=always

[Install]
WantedBy=multi-user.target
```

**Start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now proton-bridge
```

---

## Phase 2: Middleware (Postfix Relay)

We use Postfix to "bridge the bridge". It accepts mail easily and handles the hard work of talking to Proton.

### 1. Install Postfix & SASL
During installation, select **"Satellite system"**.
*   **System mail name:** (e.g., `hostname.yourdomain.com`)
*   **SMTP relay host:** `[127.0.0.1]:1025`

```bash
sudo apt install -y postfix libsasl2-modules sasl2-bin
```

### 2. Configure Incoming Authentication (SASL)
Many Docker apps (like Zitadel) require authentication to send email. We set up a local user for this.

**A. Create User:**
```bash
sudo useradd zitadel
sudo passwd zitadel
# Set a password (e.g., "zitadel")
```

**B. Configure SASL Daemon:**
1.  Edit `/etc/postfix/sasl/smtpd.conf`. Content: **See `mail/smtpd.conf.example`**.
2.  Edit `/etc/default/saslauthd`. Content: **See `mail/saslauthd.example`**.

**C. Fix PID File Location (Crucial for Systemd):**
The custom run path requires a systemd override.
```bash
sudo systemctl edit saslauthd
```
Paste this content:
```ini
[Service]
PIDFile=/var/spool/postfix/var/run/saslauthd/saslauthd.pid
```

**D. Permissions & Restart SASL:**
```bash
sudo mkdir -p /var/spool/postfix/var/run/saslauthd
sudo chown -R root:sasl /var/spool/postfix/var/run/saslauthd
sudo chmod 710 /var/spool/postfix/var/run/saslauthd
sudo adduser postfix sasl
sudo systemctl restart saslauthd
```

### 3. Configure Outgoing Authentication (Bridge)
Create the password map file with credentials from the Bridge CLI (Phase 1, Step 5).

`sudo nano /etc/postfix/sasl_passwd`
Content: **See `mail/sasl_passwd.example`**.

**Secure and Hash the file:**
```bash
sudo chmod 600 /etc/postfix/sasl_passwd
sudo postmap /etc/postfix/sasl_passwd
```

### 4. Configure `main.cf`
Edit `/etc/postfix/main.cf` to bind everything together. Ensure these lines exist:

```bash
# RELAY CONFIGURATION
# The brackets [] prevent DNS lookups (crucial for localhost)
relayhost = [127.0.0.1]:1025

# AUTHENTICATION (Outgoing to Bridge)
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous

# TLS SETTINGS (Outgoing to Bridge)
smtp_tls_security_level = may

# NETWORK SECURITY
# Only allow this server (localhost) to send mail
mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128 172.18.0.0/16
inet_interfaces = all

# AUTHENTICATION (Incoming from local clients like Zitadel)
smtpd_sasl_auth_enable = yes
smtpd_sasl_security_options = noanonymous
smtpd_sasl_local_domain = $myhostname
broken_sasl_auth_clients = yes
```
**Note:** `myhostname` should be set to `auth.kylehub.dev` in your `/etc/postfix/main.cf`.

### 5. Restart Postfix
```bash
sudo systemctl restart postfix
```

---

## Phase 3: Integration (Zitadel & Others)

Now that Postfix is accepting auth, configure your apps.

### General Configuration for ANY App
*   **SMTP Host:** `172.18.0.1` (Docker Bridge Gateway IP) or `127.0.0.1` (if local).
*   **SMTP Port:** `25`
*   **TLS/SSL:** `None` / `False` / `Off`
*   **Username:** `zitadel`
*   **Password:** `zitadel` (The password you set in Phase 2, Step 2A).
*   **Sender Address:** **MUST** match an active address or alias in your Proton account (e.g., `noreply@yourdomain.com`).

### Specific: Zitadel Configuration
If configuring via the Zitadel Console or `defaults.yaml`:

```yaml
SMTPConfiguration:
  Host: "172.18.0.1"
  Port: 25
  SenderName: "Zitadel Identity"
  SenderAddress: "noreply@yourdomain.com"
  TLS: false
  User: "zitadel"
  Password: "zitadel"
```

---

## Testing

1.  **Test Postfix Relay:**
    ```bash
    echo "This is a test email." | mail -s "Test Subject" your-personal-email@gmail.com
    ```

2.  **Check Logs:**
    *   **Postfix:** `tail -f /var/log/mail.log`
    *   **Bridge:** `tail -f /var/log/proton-bridge/bridge.log`

3.  **Troubleshooting:**
    *   **Error:** *Client host rejected: Access denied* -> Check `mynetworks` in `main.cf`.
    *   **Error:** *Certificate verification failed* -> Ensure `smtp_tls_security_level = may` in `main.cf`.
    *   **Error:** `File has unexpected size` or `Mirror sync in progress?` during `sudo apt update` -> This indicates a temporary issue with a specific package mirror. The core `apt install` command may still succeed. If not, try clearing the apt lists cache: `sudo rm -rf /var/lib/apt/lists/* && sudo apt update`.
    *   **Error:** `dpkg: dependency problems prevent configuration of protonmail-bridge` -> If `sudo dpkg -i proton-bridge.deb` fails due to unmet dependencies, run `sudo apt install -f` to install the missing packages and configure the bridge. Then, re-run `sudo dpkg -i proton-bridge.deb` to complete the installation.
