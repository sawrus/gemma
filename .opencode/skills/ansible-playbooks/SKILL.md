---
name: ansible-playbooks
type: skill
description: Write idempotent Ansible playbooks and roles for server configuration, K8s node provisioning, and application bootstrap.
related-rules:
  - iac-standards.md
  - secret-hygiene.md
allowed-tools: Read, Write, Edit, Bash
agentic:
  generated_by: agentic
  source: "areas/devops/infrastructure/skills/ansible-playbooks/SKILL.md"
  repository: "https://github.com/sawrus/agent-guides"
---

# Skill: Ansible Playbooks

> **Expertise:** Idempotent roles, inventory patterns, Vault integration, molecule testing, bare-metal K8s node prep.

## When to load

When configuring bare-metal servers, provisioning K8s nodes, managing OS-level config, or rotating OS credentials.

## Role Structure (Standard)

```
roles/base-server/
├── tasks/
│   ├── main.yml         ← imports sub-task files
│   ├── packages.yml
│   ├── sysctl.yml
│   └── users.yml
├── defaults/
│   └── main.yml         ← all variables with sensible defaults
├── vars/
│   └── main.yml         ← internal constants (not overridable)
├── templates/
│   └── sysctl.conf.j2
├── handlers/
│   └── main.yml         ← restart services on change
└── meta/
    └── main.yml         ← role dependencies
```

## Idempotency Patterns

```yaml
# ✅ Package install — idempotent
- name: Install required packages
  ansible.builtin.apt:
    name:
      - containerd
      - curl
      - jq
    state: present
    update_cache: true
  when: ansible_os_family == "Debian"

# ✅ File with checksum validation — only copies if changed
- name: Configure containerd
  ansible.builtin.template:
    src: containerd-config.toml.j2
    dest: /etc/containerd/config.toml
    owner: root
    group: root
    mode: "0644"
  notify: Restart containerd     # handler only fires if file changed

# ✅ Service management
- name: Enable and start containerd
  ansible.builtin.systemd:
    name: containerd
    enabled: true
    state: started
    daemon_reload: true
```

## Handlers Pattern

```yaml
# handlers/main.yml
- name: Restart containerd
  ansible.builtin.systemd:
    name: containerd
    state: restarted

- name: Reload sysctl
  ansible.builtin.command: sysctl --system
  changed_when: false
```

## Inventory Structure

```ini
# inventory/production/hosts.ini
[control_plane]
cp-01 ansible_host=192.168.10.10
cp-02 ansible_host=192.168.10.11
cp-03 ansible_host=192.168.10.12

[workers]
worker-01 ansible_host=192.168.10.20
worker-02 ansible_host=192.168.10.21

[k8s_cluster:children]
control_plane
workers

[k8s_cluster:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/infra-key
ansible_python_interpreter=/usr/bin/python3
```

## Vault for Secrets

```bash
# Encrypt a vars file
ansible-vault encrypt group_vars/all/vault.yml

# Inline encrypted variable
ansible-vault encrypt_string 'supersecretpassword' --name 'db_password'
```

```yaml
# group_vars/all/vault.yml (encrypted)
vault_db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  ...

# group_vars/all/vars.yml (plain, references vault vars)
db_password: "{{ vault_db_password }}"
```

## K8s Node Prep Playbook (bare-metal)

```yaml
# playbooks/k8s-node-prep.yml
---
- name: Prepare K8s nodes
  hosts: k8s_cluster
  become: true
  roles:
    - role: base-server          # OS hardening, packages
    - role: k8s-prereqs          # swap off, kernel modules, sysctl
    - role: containerd           # install + configure containerd
    - role: kubeadm-install      # install kubeadm, kubelet, kubectl (pinned)
```

## Running Playbooks

```bash
# Dry run (check mode)
ansible-playbook -i inventory/production/hosts.ini \
  playbooks/k8s-node-prep.yml --check --diff

# Run with vault password
ansible-playbook -i inventory/production/hosts.ini \
  playbooks/k8s-node-prep.yml \
  --vault-password-file ~/.ansible-vault-password

# Limit to specific hosts
ansible-playbook -i inventory/production/hosts.ini \
  playbooks/k8s-node-prep.yml \
  --limit "worker-01,worker-02"

# Tags for partial runs
ansible-playbook ... --tags "packages,sysctl" --skip-tags "users"
```

## Lint & Test

```bash
# Lint (enforce best practices)
ansible-lint playbooks/k8s-node-prep.yml

# Molecule test (spins container, runs playbook, verifies)
cd roles/base-server && molecule test
```
