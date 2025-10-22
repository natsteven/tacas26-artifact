#!/bin/bash
set -euo pipefail

echo "Installing benchexec and dependencies..."
sudo apt install -y --install-recommends ./benchexec_*.deb
sudo apt install -y openjdk-8-jdk

# Allow unprivileged user namespaces (quiet)
sudo sysctl -q -w kernel.apparmor_restrict_unprivileged_userns=0 >/dev/null 2>&1 || true

uid="$(id -u)"

# Enable cpuset on parent cgroups (quiet)
enable_cpuset() {
  local dir="$1"
  local stc="$dir/cgroup.subtree_control"
  local ctrls="$dir/cgroup.controllers"
  [[ -f "$stc" && -f "$ctrls" ]] || return 0
  if grep -qw cpuset "$ctrls"; then
    echo +cpuset | sudo tee "$stc" >/dev/null 2>&1 || true
  fi
}

enable_cpuset "/sys/fs/cgroup/user.slice"
enable_cpuset "/sys/fs/cgroup/user.slice/user-$uid.slice"
enable_cpuset "/sys/fs/cgroup/user.slice/user-$uid.slice/user@$uid.service"

# Pre-create benchexec.slice quietly without running BenchExec
systemd-run --user --unit=benchexec-bootstrap --slice=benchexec.slice --scope sleep 0.2 >/dev/null 2>&1 || true

benchexec_cg="/sys/fs/cgroup/user.slice/user-$uid.slice/user@$uid.service/benchexec.slice"

# Wait briefly for slice to appear
for _ in {1..50}; do
  [[ -d "$benchexec_cg" ]] && break
  sleep 0.05
done

# Enable cpuset on benchexec.slice (quiet)
if [[ -d "$benchexec_cg" ]]; then
  enable_cpuset "$benchexec_cg"
fi

# Stop the bootstrap scope (quiet)
systemctl --user stop benchexec-bootstrap.scope >/dev/null 2>&1 || true

echo "Init complete."