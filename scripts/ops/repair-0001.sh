#!/bin/bash
# action=repair-0001：0001 装机（单 agent，ecs-0001，标签 V100,V100-0001）。
# 原 repair-v100-0001.yml。与 0002 彻底隔离：token 现场 mint（PROD_GH_TOKEN），用完即弃。
set -uo pipefail
. "$(dirname "$0")/common.sh"
require_env V100_SSH_PASS PROD_GH_TOKEN PROD_HCLOUD_AK PROD_HCLOUD_SK
setup_ssh

INSTANCE_ID="${V100_0001_INSTANCE:-c5b805bd-5e8d-4ba5-a5ab-7523244da0fa}"

echo "[ops] 1/5 开机 $INSTANCE_ID"
echo "y" | hcloud ECS BatchStartServers --cli-region="cn-north-4" \
  --cli-access-key="$PROD_HCLOUD_AK" --cli-secret-key="$PROD_HCLOUD_SK" \
  --os-start.servers.1.id="$INSTANCE_ID" || true

for i in $(seq 1 12); do
  sleep 60
  ST=$(hcloud ECS ListServersDetails --cli-region="cn-north-4" \
        --cli-access-key="$PROD_HCLOUD_AK" --cli-secret-key="$PROD_HCLOUD_SK" --limit=25 2>/dev/null \
        | python3 -c "import json,sys;d=json.load(sys.stdin);print([s['status'] for s in d['servers'] if s['id']=='$INSTANCE_ID'][0])" 2>/dev/null || echo UNKNOWN)
  echo "  poll $i: $ST (want ACTIVE)"
  [ "$ST" = "ACTIVE" ] && { echo "  power-verified: ACTIVE"; break; }
  [ "$i" = "12" ] && { echo "[ops] FAIL: 12 分钟未 ACTIVE" >&2; exit 1; }
done

echo "[ops] 2/5 mint 注册 token"
RESP=$(curl -sS -m 30 -X POST -H "Authorization: Bearer $PROD_GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/link-seek/partner-vla-eval/actions/runners/registration-token)
TOKEN=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('token',''))")
[ -n "$TOKEN" ] || { echo "[ops] FAIL: mint 失败 $(echo "$RESP" | head -c 200)" >&2; exit 1; }
mask "$TOKEN"

echo "[ops] 3/5 装 agent"
TAG=$(curl -sS -m 30 https://api.github.com/repos/actions/runner/releases/latest \
      | python3 -c "import json,sys;print(json.load(sys.stdin)['tag_name'])")
echo "  runner version: $TAG"
read -r -d '' REMOTE <<'REMOTE'
set -euo pipefail
id runner 2>/dev/null || useradd -m -s /bin/bash runner
usermod -aG docker runner || true
mkdir -p /data/gh-runner && chown runner:runner /data/gh-runner
cd /data/gh-runner
if [ ! -f ./config.sh ]; then
  su -s /bin/bash runner -c "curl -sSL --retry 3 -o /data/gh-runner/actions-runner.tar.gz 'https://github.com/actions/runner/releases/download/$RUNNER_TAG/actions-runner-linux-x64-${RUNNER_TAG#v}.tar.gz' && tar xzf /data/gh-runner/actions-runner.tar.gz -C /data/gh-runner"
  chown -R runner:runner /data/gh-runner
fi
./svc.sh stop || true
./svc.sh uninstall || true
su -s /bin/bash runner -c "cd /data/gh-runner && ./config.sh remove --token '$REG_TOKEN' || true"
su -s /bin/bash runner -c "cd /data/gh-runner && ./config.sh --unattended --url https://github.com/link-seek/partner-vla-eval --token '$REG_TOKEN' --name ecs-0001 --labels V100,V100-0001 --work _work"
./svc.sh install runner
./svc.sh start
systemctl is-active "actions.runner.link-seek.partner-vla-eval.ecs-0001.service" || true
sleep 15
echo "listener 进程数: $(ps aux | grep -c '[R]unner.Listener')"
REMOTE
"$OPS_SSH_DIR/ssh.sh" "root@$V100_0001" "REG_TOKEN='$TOKEN' RUNNER_TAG='$TAG' bash -s" <<< "$REMOTE"
rc=$?
[ "$rc" = "0" ] || { echo "[ops] FAIL: 装 agent 退出 $rc" >&2; exit $rc; }

echo "[ops] 4/5 确认 runner 上线"
sleep 20
if [ -n "${AGENT_GITHUB_TOKEN:-}" ]; then
  GH_TOKEN="$AGENT_GITHUB_TOKEN" gh api repos/link-seek/partner-vla-eval/actions/runners \
    --jq '.runners[]|select(.name=="ecs-0001")|"\(.name) \(.status)"' | head -3 || true
fi

echo "[ops] 5/5 资产恢复（幂等：已有则跳过）"
read -r -d '' REMOTE2 <<'REMOTE2'
set -euo pipefail
DST=/data/robotwin-assets/c3ddfa8
[ -f "$DST/objects/objaverse/list.json" ] && { echo "assets already present, skip"; exit 0; }
mkdir -p "$DST"; cd /tmp
curl -sSL -o obsutil.tgz https://obs-community.obs.cn-north-1.myhuaweicloud.com/obsutil/current/obsutil_linux_amd64.tar.gz
tar -xzf obsutil.tgz
BIN=$(echo /tmp/obsutil_linux_amd64_*/obsutil)
$BIN cp obs://so101-sim-pipeline/assets/robotwin/c3ddfa8b97d5519efa828b075999bd0006778e5e/assets.tar /tmp/robotwin-assets.tar \
  -e https://obs.cn-north-4.myhuaweicloud.com -i "$OBS_AK" -k "$OBS_SK" -f
tar -xf /tmp/robotwin-assets.tar -C "$DST" && rm -f /tmp/robotwin-assets.tar
test -f "$DST/objects/objaverse/list.json" && echo "assets-ok"
REMOTE2
"$OPS_SSH_DIR/ssh.sh" "root@$V100_0001" "OBS_AK='$PROD_HCLOUD_AK' OBS_SK='$PROD_HCLOUD_SK' bash -s" <<< "$REMOTE2"
echo "[ops] repair-0001 完成"
