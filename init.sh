#!/bin/bash
set -euo pipefail

if [[ ! -e "/home/tacas" ]]; then
  echo "WARNING: This script is intended for the TACAS '26 VM environment."
  echo "Proceeding may lead to unexpected results."
  read -p "Continue? (y/n) " response || exit 1
  response=${response,,}
  if [[ -n "$response" && "$response" != "y" && "$response" != "yes" ]]; then
    echo "Aborted"
    exit 0
  fi
fi

echo "Installing benchexec and dependencies..."
sudo apt update -y
sudo apt install -y --install-recommends ./util/benchexec_*.deb
sudo apt install -y openjdk-8-jdk
sudo apt install -y parallel
sudo apt install -y maven
python3 -m venv .venv
.venv/bin/pip install pandas matplotlib

# Allow unprivileged user namespaces (quiet)
sudo sysctl -q -w kernel.apparmor_restrict_unprivileged_userns=0 >/dev/null 2>&1 || true

uid="$(id -u)"

# The following is a workaround for a kernel bug effecting benchexec using cgroups
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

systemd-run --user --unit=benchexec-bootstrap --slice=benchexec.slice --scope sleep 0.2 >/dev/null 2>&1 || true

benchexec_cg="/sys/fs/cgroup/user.slice/user-$uid.slice/user@$uid.service/benchexec.slice"

for _ in {1..50}; do
  [[ -d "$benchexec_cg" ]] && break
  sleep 0.05
done

if [[ -d "$benchexec_cg" ]]; then
  enable_cpuset "$benchexec_cg"
fi

systemctl --user stop benchexec-bootstrap.scope >/dev/null 2>&1 || true

echo "Init complete."