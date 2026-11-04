# 🏠 HomeNotifications

An extensible, production-ready Python Telegram bot, home automation daemon, and Web Management Console that provides continuous infrastructure observability, proactive device health monitoring, network discovery, and security alerting for homelabs.

---

## ✨ System Highlights

- 🖥️ **Modern Web Management Console**:
  - Full-featured left-sidebar dashboard with light/dark theme preference persistence.
  - **Sortable Inventory Tables**: Monitored devices and ARP discovery tables with clickable sort headers for every column.
  - **Device & Service Editor**: Create, modify, and delete devices, ICMP ping parameters, SSH telemetry settings, and TCP/HTTP ports directly in the browser with atomic persistence to `devices.yaml`.
  - **Comprehensive Feature Manager**: Dedicated UI tab to tweak every feature module and sub-option, including check intervals, alert thresholds, and notification modes (`immediate`, `batched`, `on_change`, `periodic`, `never`).
  - **Live Telegram Bot Controls**: Configure Bot Token, Chat ID, and Parse Mode on the fly. Includes Master On/Off switch, quick-snooze timers (15m, 1h, 4h, 8h, 24h), live countdown timer, and one-click notification resume.

- 🔐 **OpenID Connect (OIDC) Authentication & API Security**:
  - **Zero-Trust Web UI & API Protection**: Enforce authentication across both browser views and the REST API backend.
  - **Identity Provider Compatibility**: Works with Authentik, Keycloak, Authelia, Google, Okta, Zitadel, and Microsoft Entra.
  - **Seamless Browser Login Flow**: Unauthenticated browser visits automatically redirect to the IdP via the standard OIDC Authorization Code Flow.
  - **Stateless Signed Session Cookies**: Secure HTTP-only cookies (`SameSite=Lax`, optional `Secure` flag for TLS) with automatic session expiry.
  - **REST API Authentication**: Accepts either browser session cookies or `Authorization: Bearer <token>` / `X-API-Key: <token>` (OIDC JWTs or static API keys). Returns JSON `401 Unauthorized` for invalid or missing credentials.
  - **Access Filtering**: Optional claim-based access controls for authorized email addresses or groups/roles.
  - **Single Sign-Out**: `/auth/logout` clears local cookies, emits `Clear-Site-Data`, and redirects to the IdP's end-session endpoint.

- 🤖 **Interactive Telegram Bot Commands**:
  - `/status` — System health, active features, queue status, and device counters.
  - `/devices` (or `/hosts`) — Real-time list of all monitored hosts and reachability.
  - `/services` — Status and round-trip latency for all monitored TCP and HTTP services.
  - `/resources` — CPU load, RAM usage, and disk capacity for remote Linux servers via SSH.
  - `/scan` — Trigger an immediate asynchronous ARP network discovery scan.
  - `/new_devices` — List discovered network devices with MAC OUI vendor resolution.
  - `/ip` — View external WAN IPv4 address and change history.
  - `/flag` — Check US flag advisory condition and half-staff proclamations.
  - `/digest` — Immediately flush all queued batch notifications.
  - `/help` — List all available commands and explanations.

- 🌐 **13 Proactive Feature Modules**:
  1. 🌍 **External Public IP (`external_ip`)**: Probes public WAN IP and alerts upon ISP address changes.
  2. 🚩 **US Flag Status (`flag_status`)**: Tracks half-staff flag status and presidential proclamations.
  3. 💡 **Photolevel / Ambient Light (`photolevel`)**: Queries ambient light sensors for day/night automations.
  4. 🔍 **Network Discovery (`network_discovery`)**: Non-root ARP table sweeping with MAC vendor lookup and rogue device detection.
  5. 🩺 **Device & Service Health (`device_monitor`)**: Multi-protocol health checks (ICMP, TCP ports, HTTP/HTTPS endpoints).
  6. 🛡️ **Host Access Logs (`access_logs`)**: Audits remote `/var/log/auth.log` via SSH for brute-force attacks and failed SSH logins.
  7. 👨‍👩‍👧 **Family Presence (`presence`)**: Tracks household smartphones on WiFi to trigger arrival/departure notifications.
  8. 🔒 **SSL / TLS Certificate Expiry (`ssl_cert`)**: Validates TLS certificates across homelab domains and alerts at 14 days and 3 days before expiry.
  9. 🪝 **Inbound Alert Webhooks (`webhooks`)**: Secure token-authenticated HTTP POST endpoint (`/api/v1/webhook`) for external scripts, firewalls, and cron jobs.
  10. ⚡ **Speedtest & Latency SLA (`speedtest`)**: Evaluates broadband download speeds and latency, alerting when SLA dips below acceptable thresholds.
  11. 🔀 **Cisco Switch SNMP (`cisco_snmp`)**: Polls Cisco SG300 / managed switches for interface link flap and bandwidth saturation.
  12. 🔋 **UPS Power & Battery (`ups_monitor`)**: Probes UPS hardware via NUT or probe hosts for AC power outages and low battery states.
  13. 🦉 **Night Owl Activity (`night_owl`)**: Detects unauthorized entertainment and gaming device activity during quiet hours (e.g. 01:00-05:30).

---

## 🚀 Deployment & Installation

### Production Server Architecture (`app64`)

HomeNotifications is deployed on `app64` (`192.168.1.4`) running under `systemd` and reverse-proxied by Apache with automated TLS:

```
[ Clients / Browsers ]
         │
         ▼ (Port 443 HTTPS / TLS - Step-CA)
[ Apache Reverse Proxy ]
  ServerName: notifications.home.randomintervals.com
         │
         ▼ (ProxyPass http://127.0.0.1:8096/)
[ HomeNotifications Daemon ]
  WorkingDirectory: /opt/HomeNotifications
  Service: homenotifications.service (:8096)
```

### 1. Prerequisites & Virtual Environment

```bash
# Clone or sync repository to target
sudo mkdir -p /opt/HomeNotifications
sudo chown -R pferland:pferland /opt/HomeNotifications
cd /opt/HomeNotifications

# Create Python virtual environment
python3 -m venv --without-pip .venv
curl -sS https://bootstrap.pypa.io/pip/3.9/get-pip.py | .venv/bin/python

# Install dependencies
.venv/bin/pip install -r requirements.txt
```

### 2. Configuration Files

#### Application Configuration (`config.ini`)
```ini
[telegram]
bot_token = "YOUR_TELEGRAM_BOT_TOKEN"
chat_id = YOUR_TELEGRAM_CHAT_ID
parse_mode = HTML
enabled = true

[system]
devices_file = devices.yaml
state_file = data/state.json
log_level = INFO
web_enabled = true
web_host = 0.0.0.0
web_port = 8096

[auth]
enabled = false
issuer_url = https://auth.example.com
client_id = homenotifications
client_secret = replace_with_oidc_client_secret
redirect_uri = http://localhost:8096/auth/callback
cookie_secure = false
api_tokens = 

[feature:device_monitor]
enabled = true
interval_seconds = 60
notify_mode = batched
batch_interval_seconds = 300
alert_on_down = true
alert_on_recovery = true
cooldown_seconds = 3600

[feature:presence]
enabled = true
interval_seconds = 60
notify_mode = immediate
members = Paul:dc:a6:32:5c:27:2a

[feature:ssl_cert]
enabled = true
interval_seconds = 86400
notify_mode = on_change
warning_days = 14
critical_days = 3
```

#### Device Inventory (`devices.yaml`)
```yaml
devices:
  - id: gateway
    name: Main Gateway Router
    ip: 192.168.1.1
    mac: cc:ba:bd:d2:24:71
    tags: [network, core, router]
    monitors:
      ping:
        enabled: true
        timeout: 2.0
      services:
        - name: Web Admin
          type: http
          port: 80
          path: /
          expected_status: 200

  - id: app64
    name: RasPi 4 App64
    ip: 192.168.1.4
    mac: dc:a6:32:5c:27:2a
    tags: [server, database]
    monitors:
      ping:
        enabled: true
      services:
        - name: MySQL / MariaDB
          type: tcp
          port: 3306
        - name: SSH
          type: tcp
          port: 22
        - name: HTTPS
          type: tcp
          port: 443
      ssh:
        enabled: true
        username: pferland
        port: 22
        key_path: ""
```

---

## ⚙️ Systemd Service Management

The application runs as a managed background daemon via `/etc/systemd/system/homenotifications.service`:

```ini
[Unit]
Description=HomeNotifications Infrastructure & Security Alerting Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pferland
Group=pferland
WorkingDirectory=/opt/HomeNotifications
ExecStart=/opt/HomeNotifications/.venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=HomeNotifications
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

### Useful Commands
```bash
# Check service status
sudo systemctl status homenotifications

# Restart daemon
sudo systemctl restart homenotifications

# Live tail logs
sudo journalctl -u homenotifications -f -n 100
```

---

## 🌐 Apache Reverse Proxy & Step-CA TLS

Managed in `/etc/apache2/sites-available/045-notifications.home.randomintervals.com.conf`:

```apache
<VirtualHost *:80>
    ServerName notifications.home.randomintervals.com
    ServerAlias notifications.randomintervals.com
    DocumentRoot /var/www/html

    <Directory /var/www/html/.well-known/acme-challenge>
        Options None
        AllowOverride None
        Require all granted
    </Directory>

    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
    RewriteRule ^(.*)$ https://notifications.home.randomintervals.com$1 [R=301,L]
</VirtualHost>

<VirtualHost *:443>
    ServerName notifications.home.randomintervals.com
    ServerAlias notifications.randomintervals.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/notifications.home.randomintervals.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/notifications.home.randomintervals.com/privkey.pem

    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"

    <Location />
        Require ip 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 127.0.0.1 ::1
    </Location>

    SSLProxyEngine on
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"

    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*) ws://127.0.0.1:8096/$1 [P,L]

    ProxyPass / http://127.0.0.1:8096/
    ProxyPassReverse / http://127.0.0.1:8096/
</VirtualHost>
```

---

## 🔌 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/status` | `GET` | System health summary, active IP, device counters, and Telegram state |
| `/api/devices` | `GET`, `POST` | List all monitored devices or save/update device inventory |
| `/api/devices/{id}` | `PUT`, `DELETE` | Update or delete a specific device |
| `/api/devices/{id}/services` | `POST` | Add a monitored service/port to a device |
| `/api/devices/{id}/services/{idx}` | `PUT`, `DELETE` | Update or delete a service by index |
| `/api/features` | `GET`, `POST` | Retrieve or persist full feature configurations |
| `/api/features/{name}/toggle` | `POST` | Enable or disable a feature module |
| `/api/telegram` | `GET`, `POST` | Get or update Telegram bot settings |
| `/api/telegram/pause` | `POST` | Snooze / pause Telegram alerts (`{"duration_seconds": 3600}`) |
| `/api/telegram/resume` | `POST` | Resume Telegram alerts immediately |
| `/api/test/service` | `POST` | On-demand probe of a TCP or HTTP service endpoint |
| `/api/test/notification` | `POST` | Dispatch a test notification through Telegram |
| `/api/v1/webhook` | `POST` | Inbound alert webhook receiver (`X-API-Key` header authentication) |

---

## 🧪 Testing

Run the full automated test suite (all unit and integration tests):
```bash
.venv/bin/pytest -v
```

---

## 📄 License
Licensed under the Apache-2.0 License.
