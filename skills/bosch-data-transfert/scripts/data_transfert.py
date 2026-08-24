#!/usr/bin/env python3
"""
数据同步脚本 —— 通用化版本
把问题单相关数据按 TR 号拷贝到服务器目录。

支持两种数据源（通过 --src-type 或自动判断）:
  A. xlsx 表格: B列=TR号, J列=数据路径, G列=版本
  B. 清单文本: 每行 "<TR号> <数据路径>"，或用户直接给路径列表

用法:
  python3 data_transfert.py <xlsx|清单> [--dry-run] [--verify-only]
       [--src-type xlsx|list] [--src <UNC挂载前缀>] [--dst <落盘根目录>]

差异通过参数注入，无硬编码路径。
"""
import sys, os, re, subprocess, shutil, argparse

SRC_PREFIX = "/mnt/cluster"          # UNC 挂载点（//host/share -> 这里）
DEST_BASE = os.path.expanduser("~/CR60LIGHT/data/qzh")  # 落盘根，可用 --dst 覆盖
EXTENSIONS = [".bag", ".blf"]

# Excel 列（A 方案）
COL_TR = "B"
COL_DATA = "J"
COL_VER = "G"


def unc_to_local(path, src_prefix):
    """把 UNC 路径转为本地路径。src_prefix 是 //host/share 挂载点。"""
    p = path.replace("\\", "/")
    m = re.match(r"^//[^/]+/[^/]+(/.*)$", p)
    return src_prefix.rstrip("/") + (m.group(1) if m else p)


def is_unc_path(s):
    return s.startswith("\\\\") or s.startswith("//")


def resolve_source(local_path):
    """解析源路径：目录 -> 找 bag/blf；文件 -> 确认存在。返回 [(filepath,size)]"""
    if os.path.isdir(local_path):
        files = []
        for f in os.listdir(local_path):
            full = os.path.join(local_path, f)
            if os.path.isfile(full) and (f.endswith(".bag") or f.endswith(".blf")):
                files.append((full, os.path.getsize(full)))
        return files
    elif os.path.exists(local_path):
        return [(local_path, os.path.getsize(local_path))]
    else:
        for ext in EXTENSIONS:
            cand = local_path + ext
            if os.path.exists(cand):
                return [(cand, os.path.getsize(cand))]
        return []


def copy_with_retry(src, dst, retries=3):
    """带重试拷贝，校验大小。返回 'skip'/'copied'/'failed'"""
    if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
        return "skip"
    for attempt in range(retries):
        try:
            if shutil.which("rsync"):
                r = subprocess.run(["rsync", "-a", "--partial", src, dst],
                                   capture_output=True, timeout=1800)
            else:
                r = subprocess.run(["cp", src, dst], capture_output=True, timeout=1800)
            if r.returncode == 0 and os.path.getsize(dst) == os.path.getsize(src):
                return "copied"
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}")
    return "failed"


def parse_xlsx(xlsx):
    """从 Excel 提取 (TR号, 数据路径, 版本, 行号)。"""
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=False, data_only=True)
    ws = wb['Sheet1']
    entries = []
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        b = row[1] if len(row) > 1 else None
        j = row[9] if len(row) > 9 else None
        g = row[6] if len(row) > 6 else None
        if not b or not j:
            continue
        tr = str(b).strip()
        jpath = str(j).strip()
        if not is_unc_path(jpath):
            print(f"[INFO] row{i}: 跳过非路径: J列='{jpath}' (TR={tr})")
            continue
        ver = str(g).strip() if g else ""
        entries.append((tr, jpath, ver, i))
    return entries


def parse_list(path):
    """从文本清单提取 (TR号, 数据路径, "", 行号)。每行 '<TR> <路径>'"""
    entries = []
    with open(path, encoding='utf-8') as f:
        for ln, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                print(f"[INFO] line{ln}: 跳过无法解析: '{line}'")
                continue
            tr, jpath = parts[0], parts[1].strip()
            if not is_unc_path(jpath) and not os.path.exists(jpath) \
               and not os.path.exists(jpath + ".bag"):
                print(f"[INFO] line{ln}: 跳过非路径: '{jpath}' (TR={tr})")
                continue
            entries.append((tr, jpath, "", ln))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--src-type", choices=["xlsx", "list"], default=None,
                    help="自动判断或强制指定数据源类型")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--src", default=SRC_PREFIX)
    ap.add_argument("--dst", default=DEST_BASE)
    args = ap.parse_args()

    src_type = args.src_type
    if src_type is None:
        src_type = "xlsx" if args.input.endswith(".xlsx") else "list"

    entries = parse_xlsx(args.input) if src_type == "xlsx" else parse_list(args.input)
    print(f"=== 找到 {len(entries)} 条数据条目（类型: {src_type}）===")

    total_copied = 0
    total_failed = 0
    for tr, jpath, ver, rownum in entries:
        local = unc_to_local(jpath, args.src)
        tr_dir = os.path.join(args.dst, tr)
        os.makedirs(tr_dir, exist_ok=True)

        if args.verify_only:
            files = resolve_source(local)
            print(f"[VERIFY] row{rownum} {tr}: "
                  f"{'OK' if files else 'MISSING'} {local}")
            continue

        files = resolve_source(local)
        if not files:
            print(f"[WARN] row{rownum} {tr}: 源不存在: {local}")
            total_failed += 1
            continue

        print(f"[{tr}] row{rownum}: {local} -> {len(files)} 个文件")
        for src_f, size in files:
            dst_f = os.path.join(tr_dir, os.path.basename(src_f))
            if args.dry_run:
                print(f"  [DRY] {os.path.basename(src_f)} ({size / 1e6:.0f}MB)")
                continue
            result = copy_with_retry(src_f, dst_f)
            if result == "copied":
                print(f"  OK {os.path.basename(src_f)} 已拷贝")
                total_copied += 1
            elif result == "skip":
                print(f"  = {os.path.basename(src_f)} 已存在, 跳过")
            else:
                print(f"  FAIL {os.path.basename(src_f)} 拷贝失败")
                total_failed += 1

    print(f"\n=== 完成: 拷贝 {total_copied}, 失败 {total_failed} ===")


if __name__ == "__main__":
    main()