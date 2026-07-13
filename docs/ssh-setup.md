# SSH Setup Guide

This guide covers setting up SSH tunneling with LocalPort for secure access to remote
services. For the full list of SSH connection fields, see the
[Configuration Guide](configuration.md#connection).

## Prerequisites

- OpenSSH client installed
- SSH access to the target host
- Network connectivity to the target host

## Quick Start

### 1. Generate an SSH key pair

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/localport_key
ssh-copy-id -i ~/.ssh/localport_key.pub user@target-host
```

### 2. Test the connection

```bash
ssh -i ~/.ssh/localport_key user@target-host
ssh -i ~/.ssh/localport_key -p 2222 user@target-host   # non-standard port
```

### 3. Configure a LocalPort service

```yaml
version: "1.0"

services:
  - name: my-database
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: db.example.com
      user: deploy
      key_file: ~/.ssh/localport_key
      port: 22
    tags: [database]
```

### 4. Start the tunnel

```bash
localport start my-database        # a specific service
localport start --all              # all enabled services
```

## Authentication Methods

### SSH key authentication (recommended)

```yaml
connection:
  host: example.com
  user: deploy
  key_file: ~/.ssh/id_rsa
```

More secure than passwords, no interactive prompts, and easy to automate. Omit `key_file`
to fall back to your SSH agent or `~/.ssh/config`.

### Password authentication

```yaml
connection:
  host: example.com
  user: deploy
  password: ${SSH_PASSWORD}        # use an environment variable
```

Password auth requires `sshpass` and is less secure than keys:

```bash
brew install sshpass               # macOS
sudo apt-get install sshpass       # Ubuntu/Debian
sudo yum install sshpass           # CentOS/RHEL
```

## SSH Key Management

1. **Use a dedicated key for LocalPort:**
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/localport_key -C "localport-tunneling"
   ```

2. **Set correct permissions:**
   ```bash
   chmod 600 ~/.ssh/localport_key
   chmod 644 ~/.ssh/localport_key.pub
   ```

3. **Load into the SSH agent** (lets you omit `key_file` from the config):
   ```bash
   ssh-add ~/.ssh/localport_key
   ```

## Hardening with ~/.ssh/config

Define hosts once and let LocalPort reuse the settings (drop `key_file`/`user` from the
service and just point `host` at the alias):

```
# ~/.ssh/config
Host tunnel-server
    HostName db.example.com
    User deploy
    IdentityFile ~/.ssh/localport_key
    Port 22
    StrictHostKeyChecking yes
```

On the server side, disable password auth and restrict who can log in:

```
# /etc/ssh/sshd_config
PasswordAuthentication no
PubkeyAuthentication yes
AllowUsers deploy tunnel-user
```

## Bastion / Jump Hosts

To reach a service that is only accessible from inside a private network, point `host` at
the bastion and set `remote_host` to the internal target:

```yaml
services:
  - name: secure-database
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: bastion.example.com    # publicly reachable jump host
      user: jump-user
      key_file: ~/.ssh/bastion_key
      remote_host: db.internal     # target reached through the bastion
    description: "Database via bastion host"
```

LocalPort tunnels through the bastion to `remote_host:remote_port` and binds it to your
`local_port`.

## Connection Multiplexing

For multiple tunnels to the same host, reuse a single SSH connection:

```
# ~/.ssh/config
Host *.example.com
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 10m
```

## Testing and Validation

LocalPort provides built-in SSH helpers:

```bash
localport ssh test my-database                        # test a configured service
localport ssh test --host example.com --user deploy   # ad-hoc test
localport ssh validate                                # validate SSH configuration
localport ssh validate --service my-database          # validate one service
```

## Troubleshooting

For general diagnostics (logs, status, port conflicts), see the
[Troubleshooting Guide](troubleshooting.md). SSH-authentication issues usually fall into
these cases:

### Connection refused

The SSH service or port is unreachable. Verify the host and port, and check firewalls:

```bash
ssh user@host
telnet host 22
```

### Permission denied (publickey)

Key authentication failed. Check permissions and that the public key is installed:

```bash
chmod 600 ~/.ssh/localport_key
ssh -i ~/.ssh/localport_key user@host
ssh-copy-id -i ~/.ssh/localport_key.pub user@host
```

### SSH key not found

The `key_file` path is wrong or the file is missing. Confirm it exists and, if in doubt,
use an absolute path:

```bash
ls -la ~/.ssh/localport_key
# key_file: /home/user/.ssh/localport_key
```

### Debugging a connection

Run SSH directly with verbose output to see exactly where it fails:

```bash
ssh -vvv -i ~/.ssh/localport_key user@host
ssh-add -l                          # list keys loaded in the agent
```
</content>
