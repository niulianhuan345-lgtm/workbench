#!/usr/bin/env python3
"""总控台扫描器 — 扫描项目文件结构、更新 system.json。cron 定时调用。"""
import json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
ROOT = BASE.parent  # cursor123/

# ── 项目扫描配置 ──
SCAN_MAP = {
    'aione': {
        'dir': ROOT / '需求文件/AIONE',
        'subs': {
            '00-总体规划': ['*.md', '*.html'],
            '阶段一-能分析的助理': ['*/*.md'],
            '阶段二-能主动的助理': ['*/*.md'],
        }
    },
    'autoonebp': {
        'dir': ROOT / '需求文件/AutoOneBP',
        'subs': {'定时批量暂停': ['*.md', '*.html']}
    },
    'hermes': {
        'dir': ROOT / '需求文件/hermes-需求',
        'subs': {'.': ['*.md']}
    },
    'analysis': {
        'dir': ROOT / '投放分析',
        'subs': {'.': ['*.md', '*.pdf']}
    },
    'design': {
        'dir': ROOT / '产品设计',
        'subs': {'.': ['*.md']}
    },
}

def scan_dir(path, pattern):
    """递归扫描目录，返回文件树。"""
    import glob as g
    result = []
    if not path.exists():
        return result
    for pat in pattern:
        for f in sorted(g.glob(str(path / pat))):
            rel = os.path.relpath(f, ROOT)
            ext = os.path.splitext(f)[1].lower()
            ftype = 'md' if ext == '.md' else 'html' if ext == '.html' else 'pdf' if ext == '.pdf' else 'file'
            name = os.path.basename(f)
            # Check if it's in a subfolder
            subdir = os.path.relpath(os.path.dirname(f), path)
            if subdir == '.':
                result.append({'name': name, 'type': ftype, 'path': rel})
            else:
                # Find or create folder node
                parts = subdir.split(os.sep)
                node = result
                for part in parts:
                    found = next((n for n in node if n.get('name') == part and n.get('type') == 'folder'), None)
                    if not found:
                        found = {'name': part, 'type': 'folder', 'children': []}
                        node.append(found)
                    node = found.setdefault('children', [])
                node.append({'name': name, 'type': ftype, 'path': rel})
    return result


def main():
    changes = []

    # 1. Update project file trees
    proj_path = DATA / 'projects.json'
    if proj_path.exists():
        with open(proj_path, 'r', encoding='utf-8') as f:
            projects = json.load(f)
    else:
        projects = []

    for proj in projects:
        pid = proj.get('id')
        if pid not in SCAN_MAP:
            continue
        cfg = SCAN_MAP[pid]
        files = []
        for sub, patterns in cfg['subs'].items():
            sub_path = cfg['dir'] / sub if sub != '.' else cfg['dir']
            children = scan_dir(sub_path, patterns)
            if sub == '.':
                files.extend(children)
            elif children:
                files.append({'name': sub, 'type': 'folder', 'children': children})
        if files:
            proj['files'] = files
            changes.append(f'{pid}: {len(files)} 个顶层节点')

    with open(proj_path, 'w', encoding='utf-8') as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)

    # 2. Update system.json
    tasks = []
    tpath = DATA / 'tasks.json'
    if tpath.exists():
        with open(tpath) as f:
            tasks = json.load(f)

    uptime = '--'
    try:
        r = subprocess.run(['ps', '-o', 'etime=', '-p', str(os.getppid())], capture_output=True, text=True)
        if r.stdout.strip():
            uptime = r.stdout.strip()
    except:
        pass

    sys_data = {
        'agent': 'running',
        'uptime': uptime,
        'started': datetime.now().strftime('%-m/%-d %H:%M'),
        'dingtalk': '已连接',
        'cron': [
            {'name': '隧道保活', 'schedule': '*/5 * * * *', 'status': 'running'},
            {'name': '每日早安', 'schedule': '3 9 * * 1-5', 'status': 'running'},
            {'name': '周维度报告', 'schedule': '17 10 * * 1', 'status': 'running'},
            {'name': '数据同步', 'schedule': '13 */2 * * *', 'status': 'running'},
            {'name': '总控台扫描', 'schedule': '*/30 * * * *', 'status': 'running'},
        ],
        'platKB': ['万相台无界', '天猫', '京东', '小红书', '唯品会', '数据分析', '淘宝闪购', '外卖行业', '咖啡行业']
    }

    with open(DATA / 'system.json', 'w', encoding='utf-8') as f:
        json.dump(sys_data, f, ensure_ascii=False, indent=2)

    # 3. Summary
    total = len(tasks)
    done = sum(1 for t in tasks if t.get('status') == 'done')
    pending = sum(1 for t in tasks if t.get('status') == 'pending')
    ip = sum(1 for t in tasks if t.get('status') == 'in_progress')

    print(f'[{datetime.now().strftime("%H:%M")}] 扫描完成')
    print(f'  项目: {", ".join(changes) if changes else "无变化"}')
    print(f'  任务: {total} 总 · {done} 完成 · {ip} 进行中 · {pending} 待处理')


if __name__ == '__main__':
    main()
