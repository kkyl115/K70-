#!/system/bin/sh
# ============================================================
# VAS 三档调度配置应用器 (L3 策略编排层)
#
# 重要: 这是【sysfs 调参层】，不是自研内核调度器。
#       未修改 kernel/sched/ 任何代码，不触碰 GKI KMI。
#
# 需要 root。默认 dry-run，只打印将要写入的值。
# 用法:
#   sh vas_apply.sh balanced            # 预览
#   sh vas_apply.sh balanced --apply    # 实际写入
#   sh vas_apply.sh --restore           # 恢复最近一次记录的原始值
# ============================================================
set -u
PROJ=/sdcard/Download/vermeer-ultimate-kernel
STATE_DIR=$PROJ/evidence/vas_state
mkdir -p "$STATE_DIR"
MODE=dry
PROFILE=""
for a in "$@"; do
  case "$a" in
    --apply) MODE=apply ;;
    --restore) PROFILE=restore ;;
    balanced|performance|efficiency) PROFILE="$a" ;;
  esac
done

if [ "$PROFILE" = "restore" ]; then
  LAST=$(ls -t "$STATE_DIR"/orig_*.conf 2>/dev/null | head -1)
  [ -z "${LAST:-}" ] && { echo "没有可恢复的记录"; exit 1; }
  [ "$(id -u)" != "0" ] && { echo "恢复需要 root"; exit 1; }
  echo "从 $LAST 恢复:"
  while IFS='|' read -r path val; do
    [ -z "${path:-}" ] && continue
    [ -w "$path" ] || { echo "  跳过(不可写): $path"; continue; }
    echo "$val" > "$path" 2>/dev/null && echo "  恢复 $path = $val" || echo "  失败 $path"
  done < "$LAST"
  exit 0
fi

CFG="$PROJ/configs/$PROFILE/vas_profile.conf"
[ ! -f "$CFG" ] && { echo "找不到配置: $CFG"; echo "用法: vas_apply.sh balanced|performance|efficiency [--apply]"; exit 1; }

echo "=============================================="
echo " VAS profile: $PROFILE   mode: $MODE"
echo " 配置: $CFG"
echo "=============================================="

if [ "$MODE" = "apply" ] && [ "$(id -u)" != "0" ]; then
  echo "!! --apply 需要 root，当前 uid=$(id -u)"
  exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
ORIG="$STATE_DIR/orig_${TS}_${PROFILE}.conf"
: > "$ORIG"

n=0; skip=0
while IFS='|' read -r path val note; do
  case "$path" in ''|\#*) continue ;; esac
  if [ ! -e "$path" ]; then
    echo "  [SKIP] 不存在: $path   ($note)"
    skip=$((skip+1)); continue
  fi
  cur=$(cat "$path" 2>/dev/null)
  echo "  [$( [ "$MODE" = apply ] && echo APPLY || echo DRY )] $path"
  echo "         当前='$cur'  目标='$val'   # $note"
  echo "$path|$cur" >> "$ORIG"
  if [ "$MODE" = "apply" ]; then
    if echo "$val" > "$path" 2>/dev/null; then
      now=$(cat "$path" 2>/dev/null)
      [ "$now" = "$val" ] && echo "         → OK (读回=$now)" || echo "         → 写入后读回不一致: $now"
    else
      echo "         → 写入失败（可能 SELinux 或只读）"
    fi
  fi
  n=$((n+1))
done < "$CFG"

echo
echo "处理 $n 项，跳过 $skip 项"
echo "原始值已记录: $ORIG"
[ "$MODE" = apply ] && echo "回滚命令: sh $PROJ/scripts/vas_apply.sh --restore"
echo
echo "提醒: 本工具不改变 scaling_max_freq，不修改 thermal，不替换 governor。"
