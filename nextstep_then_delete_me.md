# Next step: fix `localport status` crashing on a stale/broken SSH service

> Temporary handoff note. **Delete this file when the work is done.** Do not commit it.

## Symptom

Running `localport status` dumps a mess instead of a status table: a
structured-log error blob **plus** a full Rich traceback ending in
`SSHKeyNotFoundError: SSH key file not found: ~/.ssh/api_key`. No service
status is shown at all.

The user's expectation: everything in their config is stale (points at a
long-gone `dev-hybrid-us-east-1` cluster), so `status` should simply list the
services as stopped/old — not crash.

## Root cause (three compounding problems, all in the tool)

1. **Key-file existence is checked at config *parse* time.**
   `status` → `load_services()` builds a `ConnectionInfo` per service. For SSH
   services, `ConnectionInfo.ssh()` → `_validate_ssh_config()` does
   `if not key_path.exists(): raise SSHKeyNotFoundError`. Whether a private key
   is present on disk is a *connection/runtime* concern, not a config-parsing
   concern.
2. **One bad service aborts the whole command.** That exception propagates out
   of `load_services()`, so a single broken service kills the entire `status`
   view instead of the other ~18 services rendering fine.
3. **An expected user-config error is rendered as a crash.** It surfaces as a
   structured-log dump *and* a Rich traceback. A clean CLI should print one
   line, e.g. `Service 'remote-api': SSH key not found: ~/.ssh/api_key`.

### Specific trigger
Last entry in `~/.config/localport/config.yaml`:
```yaml
- name: remote-api        # leftover placeholder / example service
  technology: ssh
  local_port: 3000
  remote_port: 3000
  connection:
    host: api.example.com
    port: 22
    user: apiuser
    key_file: ~/.ssh/api_key   # <- does not exist -> triggers the crash
    remote_host: localhost
```
(The real SSH service `trilliant-postgres` uses `~/.ssh/bastion_ssh_key.pem`,
which does exist, so it isn't the trigger.)

## Where to fix (grep, don't trust line numbers — repo is mid-refactor)

- `src/localport/domain/value_objects/connection_info.py`
  - `_validate_ssh_config()` — the `key_path.exists()` / `SSHKeyNotFoundError`
    check. This is problem #1.
  - `ssh()` classmethod calls the validation via `__post_init__`.
- `src/localport/infrastructure/repositories/yaml_config_repository.py`
  - `load_services()` — builds each `ConnectionInfo`; re-raises an enriched
    `SSHKeyNotFoundError`. This is where problem #2 lives (all-or-nothing load).
- `src/localport/cli/commands/service_commands.py`
  - `status_services_command()` — calls `await config_repo.load_services()`
    with no tolerance; this is where problem #3 (traceback vs clean message)
    surfaces.
  - Check the other read-only commands too (`list`, cluster/daemon status) —
    they likely share the same `load_services()` fragility.

Useful greps:
```
grep -rn "key_path.exists\|SSHKeyNotFoundError" src/localport
grep -rn "load_services" src/localport
```

## Suggested fix (confirm scope with the user first)

**Recommended — harden the tool so read paths degrade gracefully:**
- Stop validating key-file existence during config parsing. Either drop the
  `exists()` check from `_validate_ssh_config()` entirely, or gate it behind a
  "strict"/connect-time path so `start` still fails loudly when it actually
  tries to open the tunnel.
- Make `load_services()` (or `status`) tolerant per-service: a service that
  fails to build should be surfaced as `misconfigured`/`error` in the table
  while the rest still render. Don't let one entry abort the whole load.
- Render expected user-config errors (`SSHKeyNotFoundError`, missing fields,
  bad ports) as a concise one-line message with the service name + config
  source — no traceback, no structured-log dump to the console.

**Optional immediate relief (user's config, their call):** remove the stale
`remote-api` placeholder from `~/.config/localport/config.yaml`. The rest of
the config points at the gone `dev-hybrid-us-east-1` cluster and can likely be
pruned too — ask the user how much they want cleaned.

## Important: the running CLI is NOT this repo

`localport` on PATH is a pipx install (v1.1.1) at
`~/.local/pipx/venvs/localport/`, independent of this checkout. Source edits
here won't change the `localport` command until you reinstall.

## Verify

```
pipx install --editable /Users/ldawson/repos/localport --force   # or: pipx reinstall localport from this repo
localport status
```
Expected: a clean table of all services (kubectl ones as stopped; any
key-missing SSH service flagged `misconfigured`) — no traceback, no log blob.

## Repo state when this note was written
- Branch `chore/lint-and-readability`, **dirty working tree** (uncommitted
  changes across many files). Decide with the user whether the fix lands on
  that branch or a fresh one so it doesn't tangle with the in-progress work.
