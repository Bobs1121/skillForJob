#!/bin/bash
# CR60/BYD arbe 切分支/编译/启动 一键脚本（从 cr60light-arbe-build 通用化而来）
#
# 用法（变量可被环境/profile 覆盖）:
#   bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]
# 示例:
#   bash setup_arbe.sh BYD_UKE_BL03RC02.7 BYD_UKE
#
# 流程: 1.切tag  2.拷CUDA表  3.改yaml 53/54  4.校验仿真改动  5.catkin_make  6.(可选)bash start
#
# 所有项目差异通过环境变量注入（来自 profiles/<项目>.yml 或调用方），脚本本身无硬编码路径。
set -u

# ==== 可配置（默认 CR60/BYD）====
ARBE="${ARBE:-$HOME/CR60LIGHT/cr60_light_arbe}"          # 外仓工作区
ALGO_SUB="${ALGO_SUB:-src/algo_source}"                   # 内仓 submodule 相对路径
GIT_REMOTE="${GIT_REMOTE:-ssh://git@sourcecode01.de.bosch.com:7999/cr60_evo/cr60_light.git}"
CONFIG_SUB="${CONFIG_SUB:-src/arbe_phoenix_radar_driver-master/arbe_gui/Config}"
YAML_NAME="${YAML_NAME:-launch_config_4radars.yaml}"
CUST_SUB="${CUST_SUB:-tools/container_input/08_CustData}" # 内仓车型下 08_CustData 相对路径
CUDA_GLOB="${CUDA_GLOB:-CUDA_*.xlsx}"
SHEET_DEFAULT="${SHEET_DEFAULT:-03_QZH}"                  # 车型→sheet 默认
# 车型→sheet 映射（bash 关联数组，可通过注入不同值覆盖；这里给 CR 默认）
declare -A MODEL_SHEET=(
  [BYD_UKE]=03_QZH
  [BYD_SC6H]=03_QZH
  [SC6H]=03_QZH
)
# 仿真补丁文件（相对各自仓）: visualization_node.cpp 需补 taskTime；paraDefine.h 需 BUILDMODEL=2
VIZ_FILE="${VIZ_FILE:-src/arbe_phoenix_radar_driver-master/arbe_gui/src/arbe_visualization_engine/visualization_node.cpp}"
PARA_FILE="${PARA_FILE:-adas/symmetry/perception/include/paraDefine.h}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/noetic/setup.bash}"

ALGO="$ARBE/$ALGO_SUB"
CONFIG="$ARBE/$CONFIG_SUB"
YAML="$CONFIG/$YAML_NAME"

usage() {
  echo "用法: bash setup_arbe.sh <tag> [<车型>] [--skip-build] [--start]"
  echo "  <tag>    目标版本 tag（如 BYD_UKE_BL03RC02.7），来自问题单 G 列"
  echo "  <车型>   车型目录名（如 BYD_UKE / BYD_SC6H），默认需显式给出"
  echo "参数缺失/不明确时，需要向用户咨询，不要用默认值硬跑。"
  echo "可配置环境变量: ARBE ALGO_SUB GIT_REMOTE CONFIG_SUB YAML_NAME CUST_SUB CUDA_GLOB"
}

if [ $# -lt 1 ] || [ -z "$1" ]; then
  echo "ERROR: 缺少目标 tag/分支参数。"; usage; exit 1
fi
TAG="$1"
MODEL="${2:-}"

SKIP_BUILD=0; START_TOOL=0
for a in "${@:3}"; do
  [ "$a" = "--skip-build" ] && SKIP_BUILD=1
  [ "$a" = "--start" ] && START_TOOL=1
done

# ---- 车型校验：必须能在 coem/ 下找到对应目录，否则咨询用户 ----
if [ -z "$MODEL" ]; then
  echo "WARN: 未提供车型参数。请确认车型（如 BYD_UKE / BYD_SC6H）。"
  echo "可用车型目录:"; ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "请显式传车型，例如: bash setup_arbe.sh $TAG BYD_UKE"; exit 1
fi
if [ ! -d "$ALGO/coem/$MODEL" ]; then
  echo "ERROR: 车型目录 $MODEL 不存在于 $ALGO/coem/。"
  echo "可用车型目录:"; ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "请向用户确认正确的车型。"; exit 1
fi

SHEET="${MODEL_SHEET[$MODEL]:-$SHEET_DEFAULT}"
echo "车型=$MODEL sheet=$SHEET"

echo "=== [1/6] 内仓切 tag: $TAG ==="
cd "$ALGO" || exit 1
git fetch origin --tags 2>&1 | tail -2
if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  echo "ERROR: tag $TAG 不存在。请检查版本或咨询用户分支信息。"
  echo "可用 BL0 tag:"; git tag | grep -E "BL0[1-9]" | sort | tail -15; exit 1
fi
git checkout "$TAG" 2>&1 | tail -3
echo "当前: $(git describe --tags 2>&1)"

echo "=== [2/6] 拷贝最新 CUDA 表: $MODEL ==="
CUST="$ALGO/coem/$MODEL/$CUST_SUB"
if [ -d "$CUST" ]; then
  LATEST=$(ls -t "$CUST"/$CUDA_GLOB 2>/dev/null | head -1)
  if [ -n "$LATEST" ]; then
    cp "$LATEST" "$CONFIG/"; echo "拷贝: $(basename "$LATEST") -> $CONFIG/"
  else
    echo "ERROR: $CUST 无 CUDA xlsx 表。需要向用户咨询 CUDA 表来源。"
    echo "该目录内容:"; ls -la "$CUST" 2>/dev/null; exit 1
  fi
else
  echo "ERROR: 车型 CUDA 目录不存在: $CUST"
  echo "存在车型:"; ls -d "$ALGO"/coem/*/ 2>/dev/null | xargs -n1 basename 2>/dev/null
  echo "请向用户确认正确的车型或 CUDA 表位置。"; exit 1
fi

echo "=== [3/6] 更新 yaml 的 xlsx_path / xlsx_sheet 键 ==="
NEW_XLSX=$(ls -t "$CONFIG"/$CUDA_GLOB 2>/dev/null | head -1)
if [ -n "$NEW_XLSX" ]; then
  NEW_NAME=$(basename "$NEW_XLSX")
  python3 - "$YAML" "$NEW_NAME" "$SHEET" << 'PYEOF'
import sys
yaml_path, new_xlsx, new_sheet = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(yaml_path, encoding='utf-8').read().split('\n')
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('xlsx_path:'):
        lines[i] = line.replace(s, f'xlsx_path: "{new_xlsx}"')
    elif s.startswith('xlsx_sheet:'):
        lines[i] = line.replace(s, f'xlsx_sheet: "{new_sheet}"')
open(yaml_path, 'w', encoding='utf-8').write('\n'.join(lines))
print(f"yaml 更新: xlsx_path={new_xlsx}, xlsx_sheet={new_sheet}")
PYEOF
  grep -n -E "xlsx_path:|xlsx_sheet:" "$YAML" | head -5
else
  echo "WARN: Config 无 CUDA xlsx，跳过 yaml 更新"
fi

echo "=== [4/6] 校验仿真临时改动 ==="
echo "--- 外仓 visualization_node.cpp ---"
cd "$ARBE"
if git diff --quiet "$VIZ_FILE" 2>/dev/null; then
  echo "WARN: $VIZ_FILE 无改动！需要 taskTime 补丁"
else
  git diff "$VIZ_FILE" 2>&1 | grep -E "^[+-].*taskTime" | head -3
fi
echo "--- 内仓 paraDefine.h ---"
cd "$ALGO"
if grep -q "#define BUILDMODEL 2" "$PARA_FILE" 2>/dev/null; then
  echo "OK: BUILDMODEL=2 (ROS GUI mode)"
else
  echo "WARN: $PARA_FILE 未设置 BUILDMODEL 2。当前:"; grep -n "define BUILDMODEL" "$PARA_FILE" 2>/dev/null
fi

if [ "$SKIP_BUILD" = "1" ]; then
  echo "=== 跳过编译 (--skip-build) ==="
  echo "完成。可用: cd $ARBE && source $ROS_SETUP && catkin_make"; exit 0
fi

echo "=== [5/6] catkin_make 编译 ==="
cd "$ARBE"
source "$ROS_SETUP"
catkin_make 2>&1 | tail -20
BUILD_RC=${PIPESTATUS[0]}
if [ "$BUILD_RC" != "0" ]; then
  echo "ERROR: catkin_make 失败 (rc=$BUILD_RC)"; exit 1
fi
echo "编译成功"

if [ "$START_TOOL" = "1" ]; then
  echo "=== [6/6] bash start 启动 ==="
  cd "$ARBE"; bash start
fi

echo "=== 全部完成 ==="