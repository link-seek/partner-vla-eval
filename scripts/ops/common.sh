#!/bin/bash
# ops 公共件：SSH 包装 + 入参校验。只在 hw21 上跑（有 hcloud CLI + 到 V100 的 22 通）。
set -uo pipefail

OPS_SSH_DIR="${HOME}/.ssh-ops"
V100_0002="${V100_0002_HOST:-114.116.228.0}"
V100_0001="${V100_0001_HOST:-1.94.192.234}"
HW41_JUMP="${HW41_JUMP_HOST:-100.91.222.51}"

require_env() {   # require_env KEY...
  local missing=()
  for k in "$@"; do [ -n "${!k:-}" ] || missing+=("$k"); done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "[ops] FAIL: 缺环境变量 ${missing[*]}（应由 workflow 从 secrets 注入）" >&2
    exit 1
  fi
}

# 用 askpass 建一个可复用的 ssh 包装（V100 是密码登录；key 登录会自然忽略 askpass）
setup_ssh() {
  mkdir -p "$OPS_SSH_DIR" && chmod 700 "$OPS_SSH_DIR"
  cat > "$OPS_SSH_DIR/askpass.sh" <<'EOA'
#!/bin/sh
echo "$V100_SSH_PASS"
EOA
  chmod 700 "$OPS_SSH_DIR/askpass.sh"
  cat > "$OPS_SSH_DIR/ssh.sh" <<'EOS'
#!/bin/sh
export SSH_ASKPASS="$HOME/.ssh-ops/askpass.sh"
export SSH_ASKPASS_REQUIRE=force
export DISPLAY=:0
exec setsid ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 "$@"
EOS
  chmod 700 "$OPS_SSH_DIR/ssh.sh"
}

# v100_ssh <host> <remote-cmd>
v100_ssh() { "$OPS_SSH_DIR/ssh.sh" "root@$1" "$2"; }

# mask <value>：把敏感值从日志里抹掉（Actions 命令；本地跑只是不打印）
mask() {
  [ -n "${1:-}" ] || return 0
  if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::add-mask::$1"; fi
}

# 打印远端退出码并原样返回
run_remote() {   # run_remote <host> <script-file> [env...]
  local host="$1" script="$2"; shift 2
  local rc=0
  "$OPS_SSH_DIR/ssh.sh" "root@$host" "$* bash -s" < "$script" || rc=$?
  echo "[ops] remote($host) exit=$rc"
  return $rc
}
