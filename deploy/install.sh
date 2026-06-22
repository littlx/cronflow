#!/usr/bin/env bash
#
# CronFlow systemd 安装脚本 — 一次性把后端 venv + 前端 dist + systemd unit
# 部署到目标服务器上的标准目录, 并启用服务。
#
# 默认布局 (可通过环境变量覆盖):
#   /opt/cronflow/backend         后端源码 + venv  (来自 ./backend)
#   /opt/cronflow/frontend        前端打包 dist    (来自 ./frontend/dist)
#   /var/lib/cronflow             数据目录 (SQLite + WAL)
#   /etc/cronflow/cronflow.env    运行配置 (override)
#   /etc/systemd/system/cronflow.service
#
# 用法 (在仓库根目录, sudo 权限):
#   sudo bash deploy/install.sh
#
# 升级 (拉新代码后重新执行即可, 会保留 /var/lib/cronflow 数据):
#   sudo bash deploy/install.sh
#
set -euo pipefail

PREFIX="${PREFIX:-/opt/cronflow}"
DATA_DIR="${DATA_DIR:-/var/lib/cronflow}"
ETC_DIR="${ETC_DIR:-/etc/cronflow}"
USER_NAME="${USER_NAME:-cronflow}"
GROUP_NAME="${GROUP_NAME:-cronflow}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_NAME="cronflow"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> CronFlow 部署 (PREFIX=$PREFIX, DATA_DIR=$DATA_DIR)"

if [[ "$EUID" -ne 0 ]]; then
    echo "ERROR: 请用 sudo / root 运行" >&2
    exit 1
fi

# ---- 1) 系统用户 ----
if ! id -u "$USER_NAME" >/dev/null 2>&1; then
    echo "==> 创建系统用户 $USER_NAME"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$USER_NAME"
fi

# ---- 2) 目录 ----
echo "==> 创建目录结构"
mkdir -p "$PREFIX/backend" "$PREFIX/frontend" "$DATA_DIR" "$ETC_DIR"

# ---- 3) 后端源码 + venv ----
echo "==> 同步后端源码"
# 排除 venv / 缓存 / DB, 但保留 alembic / app / tasks / pyproject
rsync -a --delete \
    --exclude ".venv/" \
    --exclude "__pycache__/" \
    --exclude "*.db" --exclude "*.db-wal" --exclude "*.db-shm" --exclude "*.db-journal" \
    "$REPO_ROOT/backend/" "$PREFIX/backend/"

echo "==> 创建/更新 venv"
if [[ ! -d "$PREFIX/backend/.venv" ]]; then
    "$PYTHON_BIN" -m venv "$PREFIX/backend/.venv"
fi
"$PREFIX/backend/.venv/bin/pip" install --upgrade pip
"$PREFIX/backend/.venv/bin/pip" install --upgrade -e "$PREFIX/backend"

# ---- 4) 前端 dist ----
if [[ ! -d "$REPO_ROOT/frontend/dist" ]]; then
    echo "ERROR: $REPO_ROOT/frontend/dist 不存在, 请先在前端目录执行 npm run build" >&2
    exit 1
fi
echo "==> 同步前端 dist"
rsync -a --delete "$REPO_ROOT/frontend/dist/" "$PREFIX/frontend/"

# ---- 5) 环境配置 ----
if [[ ! -f "$ETC_DIR/cronflow.env" ]]; then
    echo "==> 安装默认 env 文件到 $ETC_DIR/cronflow.env"
    install -m 0640 "$SCRIPT_DIR/cronflow.env.example" "$ETC_DIR/cronflow.env"
fi

# ---- 6) 权限 ----
echo "==> 设置权限"
chown -R "$USER_NAME:$GROUP_NAME" "$PREFIX" "$DATA_DIR" "$ETC_DIR"
# 数据目录可写, 安装目录只读
chmod 750 "$DATA_DIR" "$ETC_DIR"

# ---- 7) systemd unit ----
echo "==> 安装 systemd unit"
install -m 0644 "$SCRIPT_DIR/cronflow.service" "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

# ---- 8) 启动 / 重启服务 ----
if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    echo "==> 重启 $SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
else
    echo "==> 启用并启动 $SERVICE_NAME"
    systemctl enable --now "$SERVICE_NAME"
fi

echo ""
echo "==> 完成。常用命令:"
echo "    systemctl status  $SERVICE_NAME"
echo "    systemctl restart $SERVICE_NAME"
echo "    journalctl -u $SERVICE_NAME -f"
echo ""
echo "    访问:  http://<server-ip>:8123/"
echo "    配置:  $ETC_DIR/cronflow.env"
echo "    数据:  $DATA_DIR/cronflow.db"
