#!/usr/bin/env python3
"""
Repo Profiler - 自动构建代码仓画像

用法:
    python analyze_repo.py --mode full --output .claude/repo_profile.json
    python analyze_repo.py --mode incremental --output .claude/repo_profile.json

无需额外依赖，仅使用 Python 标准库 + git/ripgrep CLI。
如果 ripgrep 不可用，自动回退到 grep。
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


SCHEMA_VERSION = "1.0"
SAMPLE_SIZE = 30
GIT_HISTORY_DEPTH = 100
GENERATED_DIR_PATTERNS = {"gen", "generated", "build", "out", "__pycache__", "node_modules", ".git"}

# 常见源码扩展名
SOURCE_EXTENSIONS = {
    "cpp": {".cpp", ".cc", ".cxx", ".c++"},
    "c": {".c"},
    "header": {".h", ".hpp", ".hxx", ".hh"},
    "python": {".py"},
    "java": {".java"},
    "rust": {".rs"},
    "go": {".go"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx"},
}

ALL_SOURCE_EXTS = set()
for exts in SOURCE_EXTENSIONS.values():
    ALL_SOURCE_EXTS.update(exts)


def _get_shell():
    """Get the appropriate shell for running Unix commands.
    On Windows, prefer Git Bash; on Unix, use default shell.
    """
    if sys.platform == "win32":
        # Try common Git Bash locations on Windows
        candidates = [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
        ]
        for bash in candidates:
            if os.path.exists(bash):
                return bash
        # Fallback: hope 'bash' is on PATH
        return "bash"
    return None  # Use default shell on Unix


_SHELL = _get_shell()


def run_cmd(cmd, cwd=None, timeout=30):
    """运行命令并返回 stdout，失败返回空字符串。
    On Windows, runs via Git Bash to ensure Unix commands work.
    Uses errors='replace' to handle non-UTF8 output gracefully.
    """
    try:
        kwargs = dict(capture_output=True, cwd=cwd, timeout=timeout)
        if _SHELL:
            proc = subprocess.Popen(
                [_SHELL, "-c", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd
            )
        else:
            proc = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd
            )
        try:
            stdout_bytes, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return ""
        return stdout_bytes.decode("utf-8", errors="replace").strip()
    except (FileNotFoundError, OSError):
        return ""


def has_tool(tool_name):
    """检查系统是否有某个工具"""
    return bool(run_cmd(f"which {tool_name} 2>/dev/null || where {tool_name} 2>/dev/null"))


def to_unix_path(path_str):
    """Convert Windows path to Unix-style for Git Bash compatibility.
    e.g., C:\\Users\\foo -> /c/Users/foo
    """
    s = str(path_str).replace("\\", "/")
    # Convert drive letter: C:/xxx -> /c/xxx
    import re as _re
    m = _re.match(r'^([A-Za-z]):/(.*)', s)
    if m:
        return f"/{m.group(1).lower()}/{m.group(2)}"
    return s


class RepoProfiler:
    def __init__(self, repo_root, output_path):
        self.repo_root = Path(repo_root).resolve()
        self.repo_root_unix = to_unix_path(self.repo_root)
        self.output_path = Path(output_path).resolve()
        self.profile = {"schema_version": SCHEMA_VERSION}
        self.has_rg = has_tool("rg")
        self.search_cmd = "rg" if self.has_rg else "grep -r"

    def profile_full(self):
        """全量 profiling"""
        print("[Profile] Starting full repo profiling...")
        start = time.time()

        self._detect_language_and_build()
        self._build_module_map()
        self._infer_conventions()
        self._extract_safety_patterns()
        self._build_impact_rules()
        self._identify_risk_hotspots()

        elapsed = time.time() - start
        self.profile["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.profile["profiling_time_seconds"] = round(elapsed, 1)

        self._save()
        print(f"[Profile] Done in {elapsed:.1f}s → {self.output_path}")

    def profile_incremental(self):
        """增量更新：仅刷新影响规则和热点"""
        print("[Profile] Starting incremental update...")
        start = time.time()

        if self.output_path.exists():
            with open(self.output_path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)

        self._build_impact_rules()
        self._identify_risk_hotspots()

        elapsed = time.time() - start
        self.profile["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.profile["last_update_time_seconds"] = round(elapsed, 1)

        self._save()
        print(f"[Profile] Incremental update done in {elapsed:.1f}s")

    # ─── Phase 1: Language & Build System ────────────────────────

    def _detect_language_and_build(self):
        print("  [1/6] Detecting language and build system...")
        root = self.repo_root          # Path object for Python file ops
        root_s = self.repo_root_unix   # Unix-style string for shell commands

        build_files = {
            "CMakeLists.txt": "cmake",
            "BUILD": "bazel",
            "BUILD.bazel": "bazel",
            "WORKSPACE": "bazel",
            "Makefile": "make",
            "package.json": "node",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "pom.xml": "maven",
            "build.gradle": "gradle",
            "setup.py": "python",
            "pyproject.toml": "python",
        }

        detected_build = []
        for fname, btype in build_files.items():
            matches = list(root.rglob(fname))
            # 只统计前3层目录的匹配
            shallow = [m for m in matches if len(m.relative_to(root).parts) <= 3]
            if shallow:
                detected_build.append(btype)

        # 统计源码文件语言分布 (use exact extension matching to avoid double-count)
        lang_counts = Counter()
        for ext_set_name, exts in SOURCE_EXTENSIONS.items():
            name_args = " -o ".join([f'-name "*{ext}"' for ext in exts])
            result = run_cmd(
                f'find "{root_s}" \\( {name_args} \\) -not -path "*/.git/*" -not -path "*/node_modules/*" 2>/dev/null | wc -l',
                timeout=30
            )
            try:
                count = int(result.strip())
                if count > 0:
                    lang_counts[ext_set_name] = count
            except ValueError:
                pass

        primary_lang = lang_counts.most_common(1)[0][0] if lang_counts else "unknown"

        # 尝试从 CMakeLists.txt 提取 C++ 标准
        cpp_standard = None
        cmake_content = run_cmd(f'cat "{root_s}/CMakeLists.txt" 2>/dev/null | head -100')
        std_match = re.search(r'CMAKE_CXX_STANDARD\s+(\d+)', cmake_content)
        if std_match:
            cpp_standard = f"C++{std_match.group(1)}"
        else:
            std_match = re.search(r'-std=c\+\+(\d+)', cmake_content)
            if std_match:
                cpp_standard = f"C++{std_match.group(1)}"

        self.profile["language"] = primary_lang
        self.profile["language_distribution"] = dict(lang_counts.most_common())
        self.profile["build_systems"] = list(set(detected_build))
        if cpp_standard:
            self.profile["cpp_standard"] = cpp_standard

        total_files = sum(lang_counts.values())
        self.profile["total_source_files"] = total_files
        print(f"         Language: {primary_lang}, Files: {total_files}, Build: {detected_build}")

    # ─── Phase 2: Module Map ─────────────────────────────────────

    def _build_module_map(self):
        print("  [2/6] Building module map...")
        modules = {}
        root_str = self.repo_root_unix
        root_path = self.repo_root

        # Use os.listdir for better cross-platform/submodule compatibility
        try:
            top_entries = sorted(os.listdir(str(root_path)))
        except OSError:
            top_entries = []

        for name in top_entries:
            entry_path_unix = f"{root_str}/{name}"
            entry_path_native = str(root_path / name)
            if not os.path.isdir(entry_path_native):
                continue
            if name.startswith(".") or name in GENERATED_DIR_PATTERNS:
                continue

            # Count source files using find (reliable across platforms)
            result = run_cmd(
                f'find "{entry_path_unix}" \\( -name "*.cpp" -o -name "*.cc" -o -name "*.c" '
                f'-o -name "*.h" -o -name "*.hpp" -o -name "*.py" -o -name "*.java" '
                f'-o -name "*.rs" -o -name "*.go" -o -name "*.ts" -o -name "*.js" \\) '
                f'-not -path "*/.git/*" 2>/dev/null | wc -l',
                timeout=15
            )
            try:
                file_count = int(result.strip())
            except ValueError:
                file_count = 0

            if file_count == 0:
                continue

            # Detect sub-modules
            sub_modules = []
            try:
                sub_entries = sorted(os.listdir(entry_path_native))
            except OSError:
                sub_entries = []

            for sub_name in sub_entries:
                sub_path_native = os.path.join(entry_path_native, sub_name)
                sub_path_unix = f"{entry_path_unix}/{sub_name}"
                if os.path.isdir(sub_path_native) and not sub_name.startswith("."):
                    sub_count_str = run_cmd(
                        f'find "{sub_path_unix}" \\( -name "*.cpp" -o -name "*.h" -o -name "*.py" -o -name "*.java" \\) 2>/dev/null | wc -l',
                        timeout=5
                    )
                    try:
                        if int(sub_count_str.strip()) > 10:
                            sub_modules.append(sub_name)
                    except ValueError:
                        pass

            # Check for README
            has_readme = any(
                os.path.exists(os.path.join(entry_path_native, f))
                for f in ["README.md", "ReadMe.md", "README.txt"]
            )

            # Detect generated code directories (limit depth to avoid slow traversal)
            gen_dirs = []
            gen_result = run_cmd(
                f'find "{entry_path_unix}" -maxdepth 4 -type d \\( -name "gen" -o -name "generated" \\) 2>/dev/null | head -5',
                timeout=10
            )
            if gen_result:
                for gdir in gen_result.split("\n"):
                    gdir = gdir.strip()
                    if gdir:
                        # Convert back to relative path
                        rel = gdir.replace(entry_path_unix + "/", "")
                        gen_dirs.append(rel)

            modules[name] = {
                "file_count": file_count,
                "sub_modules": sub_modules[:10],
                "has_readme": has_readme,
                "generated_dirs": gen_dirs[:5],
            }

        self.profile["modules"] = modules
        print(f"         Found {len(modules)} modules")

    # ─── Phase 3: Code Conventions ───────────────────────────────

    def _infer_conventions(self):
        print("  [3/6] Inferring code conventions...")
        conventions = {}

        # 先检查配置文件
        clang_format = self.repo_root / ".clang-format"
        if clang_format.exists():
            content = clang_format.read_text(encoding="utf-8", errors="ignore")
            conventions["has_clang_format"] = True

            indent_match = re.search(r'IndentWidth:\s*(\d+)', content)
            if indent_match:
                conventions["indent_width"] = int(indent_match.group(1))

            brace_match = re.search(r'BreakBeforeBraces:\s*(\w+)', content)
            if brace_match:
                conventions["brace_style"] = brace_match.group(1)

            tab_match = re.search(r'UseTab:\s*(\w+)', content)
            if tab_match:
                conventions["use_tab"] = tab_match.group(1)
        else:
            conventions["has_clang_format"] = False

        editorconfig = self.repo_root / ".editorconfig"
        conventions["has_editorconfig"] = editorconfig.exists()

        # 采样源文件推断约定
        sample_files = self._get_sample_files(SAMPLE_SIZE)
        if sample_files:
            member_prefixes = Counter()
            namespace_patterns = Counter()
            header_guards = Counter()

            for fpath in sample_files:
                try:
                    content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                except (OSError, UnicodeDecodeError):
                    continue

                # 成员变量前缀
                members = re.findall(r'\b([a-z]_\w+)\s*[;=]', content)
                for m in members:
                    prefix = m[:2]
                    member_prefixes[prefix] += 1

                m_members = re.findall(r'\b(m_\w+)\s*[;=]', content)
                if m_members:
                    member_prefixes["m_"] += len(m_members)

                # 命名空间
                ns = re.findall(r'namespace\s+(\w+)', content)
                for n in ns:
                    namespace_patterns[n] += 1

                # 头文件保护
                if "#pragma once" in content:
                    header_guards["#pragma once"] += 1
                elif re.search(r'#ifndef\s+\w+_H', content):
                    header_guards["#ifndef"] += 1

            if member_prefixes:
                conventions["member_prefix"] = member_prefixes.most_common(1)[0][0]
            if namespace_patterns:
                conventions["top_namespaces"] = [n for n, _ in namespace_patterns.most_common(5)]
            if header_guards:
                conventions["header_guard_style"] = header_guards.most_common(1)[0][0]

        self.profile["conventions"] = conventions
        print(f"         Conventions detected: {list(conventions.keys())}")

    # ─── Phase 4: Safety Patterns ────────────────────────────────

    def _extract_safety_patterns(self):
        print("  [4/6] Extracting safety patterns...")
        patterns = {}
        root = self.repo_root_unix

        # 断言宏
        assert_macros = self._grep_patterns(
            r'(VFC_ASSERT|DC_ASSERT|assert|ASSERT|CHECK)\s*\(',
            max_results=20
        )
        if assert_macros:
            macro_names = set()
            for line in assert_macros:
                match = re.search(r'(VFC_ASSERT|DC_ASSERT|assert|ASSERT|CHECK)', line)
                if match:
                    macro_names.add(match.group(1))
            patterns["assertion_macros"] = list(macro_names)

        # 日志宏 (only match actual function-like macros, not LOG_ prefixed constants)
        log_macros = self._grep_patterns(
            r'(DC_LOG|VFC_LOG|RB_LOG|spdlog::|LOG_TRACE|LOG_DEBUG|LOG_INFO|LOG_WARN|LOG_ERROR|LOG_FATAL)\s*\(',
            max_results=30
        )
        if log_macros:
            macro_names = set()
            for line in log_macros:
                match = re.search(r'(DC_LOG|VFC_LOG|RB_LOG|spdlog|LOG_TRACE|LOG_DEBUG|LOG_INFO|LOG_WARN|LOG_ERROR|LOG_FATAL)', line)
                if match:
                    macro_names.add(match.group(1))
            patterns["logging_macros"] = sorted(macro_names)
        else:
            # Fallback: look for common logging patterns
            patterns["logging_macros"] = ["(no standard logging macros detected)"]

        # 浮点比较方式
        float_cmp = self._grep_patterns(
            r'(isZero|epsilon|EPSILON|fabs|vfc::abs.*float|std::abs.*float)',
            max_results=20
        )
        if float_cmp:
            methods = set()
            for line in float_cmp:
                if "isZero" in line:
                    methods.add("isZero()")
                if "epsilon" in line.lower():
                    methods.add("epsilon comparison")
                if "fabs" in line or "abs" in line:
                    methods.add("abs() with threshold")
            patterns["float_comparison"] = list(methods) if methods else ["direct comparison (risk!)"]

        # 空值检查
        null_checks = self._grep_patterns(
            r'(nullptr|NULL|FUS_INVALID_INDEX|INVALID_INDEX|std::optional)',
            max_results=20
        )
        if null_checks:
            methods = set()
            for line in null_checks:
                if "nullptr" in line:
                    methods.add("nullptr")
                if "FUS_INVALID_INDEX" in line or "INVALID_INDEX" in line:
                    methods.add("INVALID_INDEX sentinel")
                if "optional" in line:
                    methods.add("std::optional")
            patterns["null_check_style"] = list(methods)

        self.profile["safety_patterns"] = patterns
        print(f"         Safety patterns: {list(patterns.keys())}")

    # ─── Phase 5: Impact Rules ───────────────────────────────────

    def _build_impact_rules(self):
        print("  [5/6] Building impact analysis rules...")
        rules = []

        # 基于目录约定的通用规则
        dir_conventions = {
            "interfaces": {"trigger": "*/interfaces/*.h*", "action": "find_all_includers", "desc": "接口变更需检查所有引用"},
            "types": {"trigger": "*Types.h*", "action": "find_all_includers", "desc": "类型定义变更需检查所有使用者"},
            "params": {"trigger": "*/params/*", "action": "grep_references", "desc": "参数变更需检查所有引用处"},
            "config": {"trigger": "*/config/*", "action": "grep_references", "desc": "配置变更需检查消费者"},
            "api": {"trigger": "*/api/*", "action": "check_compatibility", "desc": "API变更需检查兼容性"},
        }

        # 检查项目中实际存在哪些约定目录
        for dirname, rule in dir_conventions.items():
            result = run_cmd(
                f'find "{self.repo_root_unix}" -type d -name "{dirname}" -not -path "*/.git/*" 2>/dev/null | head -5',
                timeout=10
            )
            if result.strip():
                rules.append(rule)

        # 添加通用的头文件变更规则
        rules.append({
            "trigger": "*.h* modified (non-generated)",
            "action": "find_all_includers",
            "desc": "头文件变更需检查所有包含它的编译单元"
        })

        # 添加测试关联规则
        rules.append({
            "trigger": "*.cpp modified",
            "action": "find_associated_test",
            "desc": "源码变更需确认对应测试是否需要更新"
        })

        self.profile["impact_rules"] = rules
        print(f"         {len(rules)} impact rules established")

    # ─── Phase 6: Risk Hotspots ──────────────────────────────────

    def _identify_risk_hotspots(self):
        print("  [6/6] Identifying risk hotspots...")
        root = self.repo_root_unix

        # 近期高频修改文件 (use --diff-filter to only get modified files)
        git_log = run_cmd(
            f'cd "{root}" && git log --format="" --name-only --diff-filter=AM -{GIT_HISTORY_DEPTH} 2>/dev/null',
            timeout=30
        )

        file_freq = Counter()
        if git_log:
            for line in git_log.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Skip non-source files and generated code
                if not any(line.endswith(ext) for ext in ALL_SOURCE_EXTS):
                    continue
                if any(pat in line for pat in ["/gen/", "/generated/", "/build/", ".git"]):
                    continue
                file_freq[line] += 1

        hotspots = []
        for filepath, count in file_freq.most_common(20):
            if count >= 2:  # 至少被修改2次才算热点
                hotspots.append({
                    "file": filepath,
                    "recent_changes": count,
                    "reason": f"Modified {count} times in last {GIT_HISTORY_DEPTH} commits"
                })

        # Bug fix 热点（从 commit message 中识别）
        bug_fix_files = Counter()
        bug_log = run_cmd(
            f'cd "{root}" && git log --oneline -{GIT_HISTORY_DEPTH} --grep="fix" --grep="bug" --grep="revert" --all-match=false --format="%H" 2>/dev/null',
            timeout=15
        )
        if bug_log:
            for sha in bug_log.strip().split("\n")[:30]:
                sha = sha.strip()
                if sha:
                    files = run_cmd(f'cd "{root}" && git diff-tree --no-commit-id --name-only -r {sha} 2>/dev/null', timeout=5)
                    for f in files.split("\n"):
                        f = f.strip()
                        if f and any(f.endswith(ext) for ext in ALL_SOURCE_EXTS):
                            bug_fix_files[f] += 1

        for filepath, count in bug_fix_files.most_common(10):
            if count >= 2:
                # 避免重复
                existing = next((h for h in hotspots if h["file"] == filepath), None)
                if existing:
                    existing["bug_fix_count"] = count
                    existing["reason"] += f"; {count} bug-fix commits"
                else:
                    hotspots.append({
                        "file": filepath,
                        "bug_fix_count": count,
                        "reason": f"{count} bug-fix commits in recent history"
                    })

        self.profile["risk_hotspots"] = hotspots[:20]
        print(f"         {len(hotspots)} risk hotspots identified")

    # ─── Helpers ─────────────────────────────────────────────────

    def _get_sample_files(self, n):
        """获取 n 个非生成的源文件作为样本"""
        root_s = self.repo_root_unix
        result = run_cmd(
            f'find "{root_s}" \\( -name "*.cpp" -o -name "*.h" -o -name "*.hpp" -o -name "*.py" -o -name "*.java" \\) '
            f'-not -path "*/gen/*" -not -path "*/generated/*" -not -path "*/build/*" -not -path "*/.git/*" '
            f'2>/dev/null',
            timeout=30
        )
        files = [f.strip() for f in result.split("\n") if f.strip()]

        # Random sample with fixed seed for reproducibility
        if len(files) > n:
            import random
            random.seed(42)
            files = random.sample(files, n)

        return files[:n]

    def _grep_patterns(self, pattern, max_results=20):
        """在代码仓中搜索模式"""
        root_s = self.repo_root_unix
        if self.has_rg:
            cmd = f'rg --no-filename -m {max_results} "{pattern}" "{root_s}" --glob "!**/gen/**" --glob "!**/.git/**" 2>/dev/null'
        else:
            cmd = f'grep -rh --include="*.cpp" --include="*.h" --include="*.hpp" -m {max_results} "{pattern}" "{root_s}" 2>/dev/null | head -{max_results}'

        result = run_cmd(cmd, timeout=15)
        return [line for line in result.split("\n") if line.strip()] if result else []

    def _save(self):
        """保存 profile 到文件"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Repo Profiler - 构建代码仓画像")
    parser.add_argument("--mode", choices=["full", "incremental"], default="full",
                        help="Profiling mode: full (default) or incremental")
    parser.add_argument("--output", default=".claude/repo_profile.json",
                        help="Output path for profile JSON")
    parser.add_argument("--repo", default=".",
                        help="Repository root path (default: current directory)")

    args = parser.parse_args()

    profiler = RepoProfiler(args.repo, args.output)

    if args.mode == "full":
        profiler.profile_full()
    else:
        profiler.profile_incremental()


if __name__ == "__main__":
    main()
