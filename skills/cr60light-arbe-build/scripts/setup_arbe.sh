#!/bin/bash
# CR60 Light arbe 切分支/编译/启动 一键脚本
# 用法:
#   bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--skip-sim-patch]
# 示例:
#   bash setup_arbe.sh BYD_UKE_BL03RC02.7 BYD_UKE
#   bash setup_arbe.sh BYD_UKE_BL03RC02.7 BYD_UKE --skip-build
#
# 功能:
#   1. 内仓 algo_source fetch tags + checkout 到目标 tag
#   2. 从内仓 08_CustData 拷贝最新 CUDA 表到外仓 Config
#   3. 修改 launch_config_4radars.yaml 的 53(xlsx_path)/54(xlsx_sheet) 行
#   4. 校验仿真临时改动 (visualization_node.cpp + paraDefine.h)
#   5. catkin_make 编译
#   6. (可选) bash start 启动
# 用法提示（缺少必填参数时）
usage() {
  echo "用法: bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]"
  echo ""
  echo "必填参数:"
  echo "  <tag>    目标版本 tag（如 BYD_UKE_BL03RC02.7），来自问题单 G 列"
  echo "  <车型>   车型目录名（如 BYD_UKE / BYD_SC6H），来自问题单 E 列，默认 BYD_UKE"
  echo ""
  echo "参数缺失/不明确时，需要向用户咨询，不要用默认值硬跑。"
  echo "可用车型目录:"
  ls -d ~/CR60LIGHT/cr60_light_arbe/src/algo_source/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo ""
  echo "可用相关 BL0 tag（先 fetch tags）:"
  cd ~/CR60LIGHT/cr60_light_arbe/src/algo_source 2>/dev/null && git fetch origin --tags 2>/dev/null
  git tag 2>/dev/null | grep -E "BL0[1-9]" | sort | tail -15
}

set -u

ARBE=~/CR60LIGHT/cr60_light_arbe
ALGO=$ARBE/src/algo_source
CONFIG=$ARBE/src/arbe_phoenix_radar_driver-master/arbe_gui/Config
YAML=$CONFIG/launch_config_4radars.yaml

# === 输入校验：参数缺失/不明确时咨询用户 ===
if [ $# -lt 1 ] || [ -z "$1" ]; then
  echo "ERROR: 缺少目标 tag/分支参数。"
  usage
  exit 1
fi
TAG="$1"
MODEL="${2:-}"

SKIP_BUILD=0
START_TOOL=0
for a in "${@:3}"; do
  [ "$a" = "--skip-build" ] && SKIP_BUILD=1
  [ "$a" = "--start" ] && START_TOOL=1
done

# 车型校验：必须能在 coem/ 下找到对应目录，否则咨询用户
if [ -z "$MODEL" ]; then
  echo "WARN: 未提供车型参数。默认 BYD_UKE？还是其他车型？请确认。"
  echo "可用车型目录:"
  ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "（如需继续请显式传车型参数，例如 bash setup_arbe.sh $TAG BYD_UKE）"
  exit 1
fi
if [ ! -d "$ALGO/coem/$MODEL" ]; then
  echo "ERROR: 车型目录 $MODEL 不存在于 $ALGO/coem/。"
  echo "可用车型目录:"
  ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "请向用户确认正确的车型。"
  exit 1
fi

# 车型 → sheet 映射（QZH 车型默认 03_QZH）
SHEET="${SHEET:-03_QZH}"
case "$MODEL" in
  BYD_UKE) SHEET=03_QZH ;;
  BYD_SC6H) SHEET=03_QZH ;;
esac

echo "=== [1/6] 内仓切 tag: $TAG ==="
cd "$ALGO" || exit 1
git fetch origin --tags 2>&1 | tail -2
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "ERROR: tag $TAG 不存在。请检查版本或咨询用户分支信息。"
  echo "可用相关 BL0 tag:"; git tag | grep -E "BL0[1-9]" | sort | tail -15
  exit 1
fi
git checkout "$TAG" 2>&1 | tail -3
echo "当前: $(git describe --tags 2>&1)"

echo "=== [2/6] 拷贝最新 CUDA 表: $MODEL ==="
CUST="$ALGO/coem/$MODEL/tools/container_input/08_CustData"
if [ -d "$CUST" ]; then
  LATEST=$(ls -t "$CUST"/CUDA_*.xlsx 2>/dev/null | head -1)
  if [ -n "$LATEST" ]; then
    cp "$LATEST" "$CONFIG/"
    echo "拷贝: $(basename $LATEST) -> $CONFIG/"
  else
    echo "ERROR: $CUST 无 CUDA xlsx 表。需要向用户咨询正确的 CUDA 表来源。"
    echo "该目录内容:"; ls -la "$CUST" 2>/dev/null
    exit 1
  fi
else
  echo "ERROR: 车型 CUDA 目录不存在: $CUST"
  echo "存在车型:"; ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "请向用户确认正确的车型，或 CUDA 表位置。"
  exit 1
fi

echo "=== [3/6] 更新 yaml 53/54 行 ==="
# 找 Config 里最新的 CUDA 文件
NEW_XLSX=$(ls -t "$CONFIG"/CUDA_*.xlsx 2>/dev/null | head -1)
if [ -n "$NEW_XLSX" ]; then
  NEW_NAME=$(basename "$NEW_XLSX")
  python3 - "$YAML" "$NEW_NAME" "$SHEET" << 'PYEOF'
import sys
yaml_path, new_xlsx, new_sheet = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(yaml_path, encoding='utf-8').read().split('\n')
# 找到 53/54 行（xlsx_path / xlsx_sheet）
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('xlsx_path:'):
        lines[i] = line.replace(s, f'xlsx_path: "{new_xlsx}"')
    elif s.startswith('xlsx_sheet:'):
        lines[i] = line.replace(s, f'xlsx_sheet: "{new_sheet}"')
open(yaml_path, 'w', encoding='utf-8').write('\n'.join(lines))
print(f"yaml 更新: xlsx_path={new_xlsx}, xlsx_sheet={new_sheet}")
PYEOF
  sed -n '53,54p' "$YAML"
else
  echo "WARN: Config 无 CUDA xlsx，跳过 yaml 更新"
fi

echo "=== [4/6] 校验仿真临时改动 ==="
echo "--- 外仓 visualization_node.cpp ---"
cd "$ARBE"
if git diff --quiet src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp 2>/dev/null; then
  echo "WARN: visualization_node.cpp 无改动！需要 taskTime 补丁"
else
  git diff src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp 2>&1 | grep -E "^[+-].*taskTime" | head -3
fi
echo "--- 内仓 paraDefine.h ---"
cd "$ALGO"
if grep -q "#define BUILDMODEL 2" adas/symmetry/perception/include/paraDefine.h 2>/dev/null; then
  echo "OK: BUILDMODEL=2 (ROS GUI mode)"
else
  echo "WARN: paraDefine.h 未设置 BUILDMODEL 2！当前:"
  grep -n "define BUILDMODEL" adas/symmetry/perception/include/paraDefine.h 2>/dev/null
fi

if [ "$SKIP_BUILD" = "1" ]; then
  echo "=== 跳过编译 (--skip-build) ==="
  echo "完成。可用: cd $ARBE && source /opt/ros/noetic/setup.bash && catkin_make"
  exit 0
fi

echo "=== [5/6] catkin_make 编译 ==="
cd "$ARBE"
source /opt/ros/noetic/setup.bash
catkin_make 2>&1 | tail -20
BUILD_RC=${PIPESTATUS[0]}
if [ "$BUILD_RC" != "0" ]; then
  echo "ERROR: catkin_make 失败 (rc=$BUILD_RC)"
  exit 1
fi
echo "编译成功"

if [ "$START_TOOL" = "1" ]; then
  echo "=== [6/6] bash start 启动 ==="
  cd "$ARBE"
  bash start
fi

echo "=== 全部完成 ==="
