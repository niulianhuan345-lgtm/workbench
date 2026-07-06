#!/usr/bin/env python3
"""
Hermes 统一工作台 v2 — 数据采集脚本
每 30 分钟由 cron 自动执行，输出 JSON 到 data-hub/data/ 目录。

输出文件:
  - system_live.json      cron 状态 + 进程实时信息
  - projects_live.json    项目目录扫描 + 自动进度计算
  - agent_processes.json  后台 Agent 进程
  - tasks_live.json       任务列表 + AI 可代办标记
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# 配置
# ============================================================

OUTPUT_DIR = Path("/tmp/workbench/data-hub/data")
CURSOR_DIR = Path("/Users/apple/cursor123")

# 六大项目定义
PROJECTS_CONFIG = [
    {
        "id": "aione",
        "name": "AIONE",
        "dirs": ["AIONE智能层", "AIONE代码项", "hermes-需求/AIONE"],
    },
    {
        "id": "jts",
        "name": "金投赏",
        "dirs": ["金投赏项目", "金投赏AI评分方案_最终版.md", "金投赏AI评分系统_PPT大纲_v12.md"],
    },
    {
        "id": "business",
        "name": "生意管家",
        "dirs": ["平台知识", "数据分析"],
    },
    {
        "id": "andy",
        "name": "Andy数据",
        "dirs": ["店铺诊断项目"],
    },
    {
        "id": "autoone",
        "name": "AutoOneBP",
        "dirs": ["AutoOneBP"],
    },
    {
        "id": "quan",
        "name": "泉哥需求",
        "dirs": [],
    },
]

# AI 可代办关键词判定
AI_DELEGATABLE_KEYWORDS = [
    "分析", "报表", "报告", "数据", "文档", "MD", "监控",
    "统计", "汇总", "整理", "抓取", "学习", "周报", "日报",
    "开发", "代码", "skill", "Skill", "实现", "测试",
    "预算分析", "人群", "Log", "log",
]

AI_CANNOT_DELEGATE_KEYWORDS = [
    "协调", "沟通", "对接", "审批", "确认", "决策", "方向",
    "第三方", "官方", "等待", "MCP接口",
]


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 1. system_live.json
# ============================================================

def generate_system_live():
    """采集 cron 状态和 Hermes 运行信息"""
    cron_jobs = []
    system_info = {
        "hermes_status": "online",
        "model": "deepseek-v4-pro",
        "uptime": "unknown",
        "platforms": {"feishu": True, "dingtalk": True, "mcp": 3},
    }

    # 尝试读取已有 cron_jobs.json
    cron_path = OUTPUT_DIR / "cron_jobs.json"
    if cron_path.exists():
        try:
            cron_jobs = json.loads(cron_path.read_text())
        except Exception:
            pass

    # 尝试获取进程信息
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        processes = result.stdout
        # 统计关键进程
        system_info["python_processes"] = processes.count("python")
        system_info["node_processes"] = processes.count("node")
        system_info["chrome_processes"] = processes.count("chrome")
    except Exception:
        system_info["python_processes"] = 0
        system_info["node_processes"] = 0
        system_info["chrome_processes"] = 0

    data = {
        "generated_at": datetime.now().isoformat(),
        "hermes": system_info,
        "cron_jobs": cron_jobs,
        "cron_summary": {
            "total": len(cron_jobs),
            "active": sum(1 for j in cron_jobs if j.get("status") == "active"),
            "error": sum(1 for j in cron_jobs if j.get("last_status") == "error"),
        },
    }

    write_json("system_live.json", data)
    return data


# ============================================================
# 2. projects_live.json
# ============================================================

def scan_directory(path: Path, depth: int = 0, max_depth: int = 3):
    """递归扫描目录，返回文件树"""
    if depth > max_depth or not path.exists():
        return None

    if path.is_file():
        return {
            "name": path.name,
            "type": "file",
            "size": format_size(path.stat().st_size if path.exists() else 0),
        }

    children = []
    try:
        for child in sorted(path.iterdir()):
            if child.name.startswith(".") or child.name == "node_modules":
                continue
            node = scan_directory(child, depth + 1, max_depth)
            if node:
                children.append(node)
    except PermissionError:
        pass

    return {
        "name": path.name,
        "type": "folder",
        "children": children,
    }


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def compute_phase_progress(phase_str: str) -> dict:
    """
    解析阶段字符串，计算进度。
    格式: "阶段一-能分析的助理:done→阶段二-能主动的助理:in_progress→..."
    """
    if not phase_str:
        return {"current": 0, "total": 0, "percent": 0, "phases": []}

    phases = []
    done_count = 0
    for part in phase_str.split("→"):
        part = part.strip()
        if ":" in part:
            name, status = part.rsplit(":", 1)
        else:
            name, status = part, "pending"

        status_map = {"done": "done", "in_progress": "in_progress", "pending": "pending"}
        normalized = status_map.get(status, "pending")

        phases.append({"name": name.strip(), "status": normalized})
        if normalized == "done":
            done_count += 1

    total = len(phases)
    # 进行中的算 0.5
    in_progress_count = sum(1 for p in phases if p["status"] == "in_progress")
    effective = done_count + in_progress_count * 0.5

    return {
        "current": done_count,
        "total": total,
        "percent": round(effective / total * 100) if total > 0 else 0,
        "phases": phases,
    }


def generate_projects_live():
    """扫描项目目录，自动计算进度"""
    projects = []

    # 尝试读取已有 projects.json 获取结构
    existing_path = OUTPUT_DIR / "projects.json"
    existing_projects = {}
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text())
            for p in existing:
                existing_projects[p.get("id", "")] = p
        except Exception:
            pass

    for cfg in PROJECTS_CONFIG:
        pid = cfg["id"]
        ep = existing_projects.get(pid, {})

        # 合并目录扫描
        file_tree = []
        for d in cfg["dirs"]:
            full_path = CURSOR_DIR / d
            if full_path.exists():
                node = scan_directory(full_path)
                if node:
                    file_tree.append(node)

        # 计算文件总数
        def count_files(tree):
            if not tree:
                return 0
            if isinstance(tree, list):
                return sum(count_files(t) for t in tree)
            if tree.get("type") == "file":
                return 1
            return sum(count_files(c) for c in tree.get("children", []))

        total_files = sum(count_files(ft) for ft in file_tree)

        # 阶段进度
        phases_raw = ep.get("phases", "")
        phase_info = compute_phase_progress(phases_raw) if phases_raw else {"current": 0, "total": 5, "percent": 0, "phases": []}

        # 如果是 AIONE，手动设置更准确的阶段信息
        if pid == "aione" and not phases_raw:
            phase_info = compute_phase_progress(
                "阶段一-能分析的助理:done→阶段二-能主动的助理:done→阶段三-有记忆的助理:in_progress→阶段四-能进化的助理:pending→阶段五-能执行的助理:pending"
            )

        projects.append({
            "id": pid,
            "name": cfg["name"],
            "files": file_tree,
            "total_files": total_files,
            "phases": phases_raw,
            "phase_info": phase_info,
            "milestones": ep.get("milestones", []),
            "docs": ep.get("docs", []),
            "collaborators": ep.get("collaborators", []),
            "status": "active" if phase_info["percent"] < 100 else "completed",
            "deadline_warning": ep.get("deadline_warning", False),
        })

    data = {
        "generated_at": datetime.now().isoformat(),
        "projects": projects,
        "summary": {
            "total_projects": len(projects),
            "avg_progress": round(
                sum(p["phase_info"]["percent"] for p in projects) / len(projects)
            ) if projects else 0,
        },
    }

    write_json("projects_live.json", data)
    return data


# ============================================================
# 3. agent_processes.json
# ============================================================

def generate_agent_processes():
    """采集后台 Agent 进程"""
    processes = []

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) < 11:
                continue
            cmd = " ".join(parts[10:])
            # 过滤相关进程
            keywords = ["python", "node", "hermes", "claude", "cron", "chrome", "server", "watch"]
            if any(kw in cmd.lower() for kw in keywords):
                processes.append({
                    "user": parts[0],
                    "pid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "command": cmd[:120],
                })
    except Exception:
        pass

    data = {
        "generated_at": datetime.now().isoformat(),
        "processes": processes[:30],  # 最多 30 条
        "total": len(processes),
    }

    write_json("agent_processes.json", data)
    return data


# ============================================================
# 4. tasks_live.json
# ============================================================

def is_ai_delegatable(task: dict) -> bool:
    """判断任务是否 AI 可代办"""
    title = task.get("title", "")
    note = task.get("note", "")
    combined = title + note

    # 先检查不能代办的
    for kw in AI_CANNOT_DELEGATE_KEYWORDS:
        if kw in combined:
            return False

    # 再检查可以代办的
    for kw in AI_DELEGATABLE_KEYWORDS:
        if kw in combined:
            return True

    return False


def generate_tasks_live():
    """读取 tasks.json，自动标记 AI 可代办"""
    tasks = []

    tasks_path = OUTPUT_DIR / "tasks.json"
    if tasks_path.exists():
        try:
            tasks = json.loads(tasks_path.read_text())
        except Exception:
            pass

    # 为每个任务添加 ai_delegatable 标记
    for task in tasks:
        task["ai_delegatable"] = is_ai_delegatable(task)
        # 处理子任务
        for st in task.get("subtasks", []):
            st["ai_delegatable"] = is_ai_delegatable(st)

    # 统计
    status_counts = {}
    for t in tasks:
        s = t.get("status", "未知")
        status_counts[s] = status_counts.get(s, 0) + 1

    project_groups = {}
    for t in tasks:
        proj = t.get("project", "其他")
        if proj not in project_groups:
            project_groups[proj] = []
        project_groups[proj].append(t)

    data = {
        "generated_at": datetime.now().isoformat(),
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "by_status": status_counts,
            "ai_delegatable_count": sum(1 for t in tasks if t.get("ai_delegatable")),
            "in_progress": status_counts.get("进行中", 0),
            "completed": status_counts.get("已完成", 0),
            "blocked": status_counts.get("阻塞", 0),
            "today_due": 0,  # 需要更精确的 deadline 解析
        },
        "by_project": {k: len(v) for k, v in project_groups.items()},
    }

    write_json("tasks_live.json", data)
    return data


# ============================================================
# 工具函数
# ============================================================

def write_json(filename: str, data: dict):
    """写入 JSON 文件，确保中文不转义"""
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"  ✅ {filename} ({os.path.getsize(path)} bytes)")


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 60)
    print(f"Hermes 统一工作台 v2 — 数据采集")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"输出: {OUTPUT_DIR}")
    print("=" * 60)

    ensure_output_dir()

    print("\n📊 采集 system_live.json ...")
    generate_system_live()

    print("\n📁 采集 projects_live.json ...")
    generate_projects_live()

    print("\n🔧 采集 agent_processes.json ...")
    generate_agent_processes()

    print("\n📋 采集 tasks_live.json ...")
    generate_tasks_live()

    print("\n" + "=" * 60)
    print("✅ 全部数据采集完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
