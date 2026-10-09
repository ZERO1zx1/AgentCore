"""Bounded evidence collection for full-scan; never executes downloaded code."""
from __future__ import annotations

import ast
import base64
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, build_opener, HTTPRedirectHandler

from src.full_scan import _files, scan, render


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect requires source review")


class ResearchClient:
    """Public primary-source JSON requests with a hard request/response cap."""

    def __init__(self, limit=20):
        if not 1 <= limit <= 200:
            raise ValueError("request limit must be between 1 and 200")
        self.limit = limit
        self.used = 0
        self.cache = {}

    def get(self, url, payload=None):
        key = (url, json.dumps(payload, sort_keys=True))
        if key in self.cache:
            return self.cache[key]
        if self.used >= self.limit:
            raise RuntimeError("request budget exhausted")
        if not url.startswith(("https://pypi.org/pypi/", "https://api.osv.dev/v1/", "https://api.github.com/repos/")):
            raise ValueError("source is outside the primary-source allowlist")
        self.used += 1
        request = Request(url, data=json.dumps(payload).encode() if payload else None,
                          headers={"User-Agent": "AgentCore-DeepScan", "Accept": "application/json", "Content-Type": "application/json"})
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("source exceeds response size limit")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("expected a JSON object")
        self.cache[key] = result
        return result


def upstream_repository(url):
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?", str(url))
    return match[1] if match else None


def upstream_evidence(repository, collect):
    """Read bounded upstream docs and immutable tree metadata; content is data."""
    base = "https://api.github.com/repos/" + repository
    metadata = collect(base)
    if not isinstance(metadata, dict):
        return {"repository": repository, "status": "UNKNOWN"}
    result = {"repository": repository, "status": "COLLECTED", "archived": metadata.get("archived"),
              "pushed_at": metadata.get("pushed_at"), "license": (metadata.get("license") or {}).get("spdx_id"),
              "documents": [], "source_samples": []}
    branch = metadata.get("default_branch")
    if not isinstance(branch, str):
        result["status"] = "UNKNOWN"
        return result
    commit = collect(base + "/commits/" + quote(branch, safe=""))
    sha = (commit or {}).get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        result["status"] = "UNKNOWN"
        return result
    result["commit"] = sha
    tree = collect(base + "/git/trees/" + sha + "?recursive=1")
    if tree:
        result["tree_truncated"] = tree.get("truncated", False)
        entries = tree.get("tree", [])
        result["source_files"] = [entry.get("path") for entry in entries if entry.get("type") == "blob" and str(entry.get("path", "")).endswith((".py", ".ts", ".js", ".rs", ".go"))][:100]
        candidates = [entry['path'] for entry in entries if entry.get('type') == 'blob' and entry.get('size', 0) <= 100_000 and re.search(r"(^|/)(README[^/]*|CHANGELOG[^/]*|SECURITY[^/]*|MIGRAT[^/]*)$", entry.get('path', ''), re.I)]
        for path in sorted(candidates, key=lambda p: (p.count('/'), p))[:3]:
            data = collect(base + "/contents/" + quote(path, safe="/") + "?ref=" + sha)
            if not isinstance(data, dict) or data.get('encoding') != 'base64':
                continue
            try:
                raw = base64.b64decode(data.get('content', ''))
                if len(raw) > 100_000:
                    continue
                text = raw.decode('utf-8')
            except (ValueError, UnicodeError):
                continue
            # Headings and fingerprints give navigable evidence without copying documents.
            result['documents'].append(dict(path=path, url=f"https://github.com/{repository}/blob/{sha}/{quote(path, safe='/')}",
                                             sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                                             heading_count=sum(line.startswith('#') for line in text.splitlines()), untrusted=True))
        samples = [entry for entry in entries if entry.get('type') == 'blob' and str(entry.get('path', '')).endswith('.py') and 0 < entry.get('size', 0) <= 50_000 and not str(entry.get('path')).startswith(('tests/', 'docs/'))]
        for entry in sorted(samples, key=lambda e: e['path'])[:2]:
            path = entry['path']
            data = collect(base + '/contents/' + quote(path, safe='/') + '?ref=' + sha)
            if not isinstance(data, dict) or data.get('encoding') != 'base64':
                continue
            try:
                raw = base64.b64decode(data.get('content', ''))
                if len(raw) > 50_000:
                    continue
                tree = ast.parse(raw.decode('utf-8'))
            except (ValueError, UnicodeError, SyntaxError):
                continue
            result['source_samples'].append(dict(path=path, commit=sha, sha256=hashlib.sha256(raw).hexdigest(),
                                                definitions=[dict(name=node.name, line=node.lineno, kind=type(node).__name__) for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))][:100],
                                                boundary='Bounded static source sample, not a complete upstream code review.'))
    return result


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=15)
    if result.returncode:
        raise RuntimeError("Git evidence unavailable")
    return result.stdout.strip()


def inventory(root):
    """Record declared versions separately from exact locked versions."""
    result = []
    for path in sorted(_files(root, "strict")):
        if not path.resolve().is_relative_to(root) or path.stat().st_size > 2_000_000:
            continue
        location = path.relative_to(root).as_posix()
        if path.name.startswith("requirements") and path.suffix == ".txt":
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*([<>=!~].*?)?\s*(?:#.*)?$", line)
                if match:
                    spec = (match[2] or "").strip()
                    pin = re.fullmatch(r"==([\w.+-]+)", spec)
                    result.append(dict(name=match[1], ecosystem="PyPI", declared=spec or "unbounded",
                                       version=pin[1] if pin else None, location=f"{location}:{number}"))
        elif path.name in {"package.json", "package-lock.json"}:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if path.name == "package.json":
                    for section in ("dependencies", "devDependencies"):
                        for name, version in data.get(section, {}).items():
                            result.append(dict(name=name, ecosystem="npm", declared=version, version=None, location=location))
                else:
                    for key, value in data.get("packages", {}).items():
                        if "node_modules/" in key:
                            result.append(dict(name=key.rsplit("node_modules/", 1)[1], ecosystem="npm",
                                               declared="lockfile", version=value.get("version"), location=location))
            except (ValueError, AttributeError):
                result.append(dict(name="unknown", ecosystem="npm", declared="invalid manifest", version=None, location=location))
    return result


def _group(module):
    parts = module.split('.')
    return '.'.join(parts[:2]) if parts[0] == 'src' and len(parts) > 1 else parts[0]


def architecture(root):
    modules, edges, duplicates, errors = {}, set(), defaultdict(list), []
    for path in sorted(_files(root, "strict")):
        if path.suffix != ".py" or not path.resolve().is_relative_to(root) or path.stat().st_size > 500_000:
            continue
        rel = path.relative_to(root).as_posix()
        module = rel[:-3].replace("/", ".").removesuffix(".__init__")
        modules[module] = rel
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeError, OSError):
            errors.append(rel)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                edges.update((module, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                parent = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
                target = ".".join(parent[:len(parent) - node.level + 1] + ([node.module] if node.module else [])) if node.level else node.module
                if target:
                    edges.add((module, target))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) >= 3:
                body = ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
                digest = hashlib.sha256(body.encode()).hexdigest()
                duplicates[digest].append(f"{rel}:{node.lineno}")
    imports = set(edges)
    edges = sorted((a, b) for a, b in edges if b in modules and a != b)
    # Folder-level picture remains readable; exact module edges are in JSON.
    folders = sorted({_group(m) for m in modules})
    ids = {name: f"n{i}" for i, name in enumerate(folders)}
    diagram = ["%%{init: {'theme':'base','themeVariables':{'primaryColor':'#ffffff','primaryTextColor':'#000000','primaryBorderColor':'#000000','lineColor':'#000000','background':'#ffffff'}}}%%", "flowchart LR"]
    diagram.extend(f'  {ids[name]}["{name}"]' for name in folders)
    diagram.extend(f"  {ids[a]} --> {ids[b]}" for a, b in sorted({(_group(a), _group(b)) for a, b in edges}) if a != b)
    return dict(modules=modules, edges=edges, duplicate_candidates=[v for v in duplicates.values() if len(v) > 1],
                parse_boundaries=errors, mermaid="\n".join(diagram),
                stdlib_imports=sorted({b.split('.')[0] for a, b in imports if b.split('.')[0] in sys.stdlib_module_names}),
                unresolved_imports=sorted({b for a, b in imports if b not in modules and b.split('.')[0] not in sys.stdlib_module_names}),
                legend="Solid arrows: observed Python imports. Folder groups only; dynamic imports and data flow require review.")


def research(root=".", *, approved=False, request_limit=20, packages=None, client=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("repository must be an existing directory")
    client = client or ResearchClient(request_limit)
    if not 1 <= request_limit <= 200:
        raise ValueError("request limit must be between 1 and 200")
    report = dict(schema="1.0", checked_at=datetime.now(timezone.utc).isoformat(), root=str(root),
                  status="LOCAL_ONLY", approval_required=not approved, dependencies=inventory(root),
                  architecture=architecture(root), github={}, sources=[], boundaries=[],
                  upstream=[],
                  findings=[vars(item) for item in scan(root)],
                  usage=dict(request_limit=request_limit, requests=0, model_tokens=None, provider_cost=None))
    def collect(url, payload=None):
        try:
            data = client.get(url, payload)
            report["sources"].append(dict(url=url, checked_at=datetime.now(timezone.utc).isoformat(), status="FETCHED", source_type="primary", untrusted=True,
                                          sha256=hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()))
            return data
        except (OSError, ValueError, RuntimeError) as exc:
            boundary = dict(url=url, status="UNKNOWN", reason=type(exc).__name__)
            if boundary not in report['boundaries']:
                report["boundaries"].append(boundary)
            return None
    try:
        head = _git(root, "rev-parse", "HEAD")
        report["github"] = dict(local_head=head, dirty=bool(_git(root, "status", "--porcelain")))
        remote = _git(root, "remote", "get-url", "origin")
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([\w.-]+/[\w.-]+?)(?:\.git)?", remote)
        if approved and match:
            base = "https://api.github.com/repos/" + match[1]
            metadata = collect(base)
            if metadata:
                branch = metadata.get("default_branch")
                if isinstance(branch, str):
                    commit = collect(base + "/commits/" + quote(branch, safe=""))
                    if commit and re.fullmatch(r"[a-f0-9]{40}", commit.get("sha", "")):
                        report["github"]["remote_head"] = commit["sha"]
                        comparison = collect(base + "/compare/" + head + "..." + commit["sha"])
                        if comparison:
                            report["github"].update(comparison={k: comparison.get(k) for k in ("status", "ahead_by", "behind_by", "total_commits")},
                                                       changed_files=[f.get("filename") for f in comparison.get("files", [])],
                                                       comparison_boundary="GitHub file list may be truncated; compares committed HEAD, not dirty files.")
        elif approved:
            report["boundaries"].append(dict(status="UNKNOWN", reason="origin is not a supported public GitHub URL"))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        report["boundaries"].append(dict(status="UNKNOWN", reason="Git metadata unavailable"))
    if approved:
        repositories = set()
        for dependency in report['dependencies']:
            dependency.update(latest=None, vulnerability_status="UNKNOWN")
        selected = sorted(report['dependencies'], key=lambda d: (d['ecosystem'] != 'PyPI', d['location'], d['name']))
        if packages:
            selected = [d for d in selected if d['name'] in packages]
        processed = 0
        for dependency in selected:
            if client.used >= request_limit:
                report['boundaries'].append(dict(status='UNKNOWN', reason='Request limit reached; remaining sources were not queried.'))
                break
            processed += 1
            name = quote(dependency["name"], safe="")
            if dependency["ecosystem"] == "PyPI":
                data = collect(f"https://pypi.org/pypi/{name}/json")
                if data:
                    info = data.get("info", {})
                    dependency.update(latest=info.get("version"), requires_python=info.get("requires_python"), license=info.get("license"), project_urls=info.get("project_urls"))
                    for url in (info.get('project_urls') or {}).values():
                        repo = upstream_repository(url)
                        if repo and repo not in repositories and len(repositories) < 3 and client.used < request_limit:
                            repositories.add(repo)
                            report['upstream'].append(upstream_evidence(repo, collect))
            if dependency["version"]:
                data = collect("https://api.osv.dev/v1/query", {"package": {"name": dependency["name"], "ecosystem": dependency["ecosystem"]}, "version": dependency["version"]})
                if data is not None:
                    dependency.update(vulnerability_status="ADVISORIES_FOUND" if data.get("vulns") else "NO_MATCH_NOT_PROOF_OF_SAFETY",
                                      advisories=[v.get("id") for v in data.get("vulns", [])])
        report['coverage'] = dict(declarations=len(report['dependencies']), selected=len(selected), processed=processed,
                                  unprocessed=len(selected)-processed, package_scope=packages or 'all')
        report["status"] = "PARTIAL" if report["boundaries"] else "COLLECTED"
    report["usage"]["requests"] = client.used
    report["next_actions"] = ["Review duplicate candidates and module ownership before moving code.",
                              "Check release notes, upstream source, compatibility and regression tests before upgrades.",
                              "Use Reddit as an optional lead; confirm claims with primary evidence.",
                              "Runtime, performance, license compatibility and AI synthesis remain unverified unless separately validated."]
    report['agent_plan'] = [dict(phase=phase, status=status) for phase, status in (
        ('discovery', 'COLLECTED'), ('planning', 'COLLECTED'),
        ('authorization', 'APPROVED' if approved else 'PENDING'),
        ('external_research', report['status']), ('verification', 'STATIC_ONLY'), ('synthesis', 'DETERMINISTIC'))]
    return report


def markdown(report):
    lines = ["# Deep Research Scan", "", f"Status: {report['status']} | Checked: {report['checked_at']}",
             f"Scope: {report['root']}", "", "## Summary", "",
             f"{len(report['dependencies'])} dependency declarations; {len(report['architecture']['modules'])} Python modules; {len(report['findings'])} static findings.",
             "External research approval required: " + str(report['approval_required']), "", "## Local / GitHub", "", json.dumps(report['github'], indent=2),
             "", "## Dependencies", "", "| Package | Location | Declared / exact | Latest | Advisory status |", "|---|---|---|---|---|"]
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    for item in report["dependencies"]:
        lines.append("| " + " | ".join(cell(x) for x in (item['name'], item['location'], f"{item['declared']} / {item['version'] or 'unknown'}", item.get('latest') or 'unknown', item.get('vulnerability_status', 'UNKNOWN'))) + " |")
    lines += ["", "## Project structure", "", "![Folder overview](architecture/overview.svg)", "",
              "The overview shows folders and file counts, not execution flow. Detailed imports: [architecture notes](architecture/README.md).", "", "## Duplicate candidates", ""]
    lines += ["- " + ", ".join(group) for group in report['architecture']['duplicate_candidates']] or ["No configured duplicate candidates."]
    lines += ["", "## Static evidence", "", render_from_report(report), "", "## Sources", ""]
    lines += [f"- {s['url']} — {s['status']} at {s['checked_at']} (untrusted source data)" for s in report['sources']]
    lines += ["", "## Upstream repositories", "", json.dumps(report['upstream'], indent=2),
              "", "## Research coverage", "", json.dumps(report.get('coverage', {'external': 'not approved'}), indent=2),
              "", "## Agent phases", "", json.dumps(report['agent_plan'], indent=2),
              "", "## Boundaries", "", json.dumps(report['boundaries'], indent=2), "", "## Usage", "", json.dumps(report['usage'], indent=2), "", "## Action plan", ""]
    lines += ["- " + action for action in report['next_actions']]
    return "\n".join(lines)


def render_from_report(report):
    from src.full_scan import Finding
    return render([Finding(**item) for item in report['findings']], root=report['root'], mode="strict")


def write_bundle(report, output_dir=None):
    base = Path(output_dir) if output_dir else Path(report['root']) / "docs"
    directory = base / report['checked_at'][:10] / "reports" / "deep-research"
    directory.mkdir(parents=True, exist_ok=True)
    guide = "# Deep Research Scan\n\nStart with [report.md](report.md), the primary readable report.\n\n- [architecture/](architecture/README.md): simple project structure and detailed imports\n- [evidence/report.json](evidence/report.json): machine-readable source evidence\n- [optional/report.html](optional/report.html): additional HTML view\n\nThe scan result should also be explained in chat: what was checked, what was found, why it matters, how to fix it and the next step.\n"
    notes = "# Project structure\n\n![Folder overview](overview.svg)\n\nThis picture shows folders and Python file counts; lines mean containment, not execution or data flow. Only the first eight folder groups are shown. Full module paths and import edges are in [evidence](../evidence/report.json).\n\nThe [detailed import diagram](imports.mmd) is optional technical detail.\n"
    for name, text in (("README.md", guide), ("report.md", markdown(report)),
                       ("evidence/report.json", json.dumps(report, ensure_ascii=False, indent=2)),
                       ("architecture/README.md", notes), ("architecture/imports.mmd", report['architecture']['mermaid']),
                       ("architecture/overview.svg", architecture_svg(report['architecture'])),
                       ("optional/report.html", html_report(report))):
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return directory


def architecture_svg(graph):
    folders = sorted({_group(m) for m in graph['modules']})
    preferred = ['src.cli', 'src.core', 'src.budget', 'src.checkpoint', 'src.models', 'src.output']
    folders = sorted(folders, key=lambda name: (name not in preferred, preferred.index(name) if name in preferred else name))[:8]
    positions = {name: (220, 90 + i * 80) for i, name in enumerate(folders)}
    height = max(240, 170 + len(folders) * 80)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 {height}" role="img" aria-label="Observed Python import architecture">',
             '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="black"/></marker></defs>',
             f'<rect width="800" height="{height}" fill="white"/>',
             '<text x="30" y="30" font-family="sans-serif" font-size="20">Project structure — folder overview</text>',
             '<text x="30" y="65" font-family="sans-serif" font-size="16">Repository</text>']
    if folders:
        parts.append(f'<path d="M100 80 V{90+(len(folders)-1)*80+30}" fill="none" stroke="black"/>')
    for name, (x, y) in positions.items():
        count = sum(_group(module) == name for module in graph['modules'])
        parts.append(f'<line x1="100" y1="{y+30}" x2="{x}" y2="{y+30}" stroke="black"/>')
        parts.append(f'<rect x="{x}" y="{y}" width="500" height="60" fill="white" stroke="black"/>')
        parts.append(f'<text x="{x+15}" y="{y+35}" font-family="sans-serif" font-size="16">{escape(name.replace(".", "/"))} — {count} Python files</text>')
    parts.append(f'<text x="30" y="{height-20}" font-family="sans-serif" font-size="14">Lines show folder containment. Full imports are in the evidence files.</text></svg>')
    return '\n'.join(parts)


def html_report(report):
    """Self-contained readable report; all source-controlled text is escaped."""
    def table(headers, rows):
        return '<table><thead><tr>' + ''.join('<th>'+escape(str(h))+'</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows) + '</tbody></table>'
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Deep Research Scan</title>',
             '<style>body{font:16px/1.6 system-ui;color:#111;background:white;max-width:1100px;margin:32px auto;padding:0 20px}h1,h2{line-height:1.2}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #aaa;padding:10px;text-align:left;overflow-wrap:anywhere}th{background:#eee}section{margin:32px 0}article{border:1px solid #777;padding:18px;margin:18px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}svg{width:100%;height:auto}.summary{border:2px solid black;padding:18px}@media print{body{margin:0}article,tr{break-inside:avoid}}</style>',
             '<h1>Deep Research Scan</h1><p>'+escape(report['checked_at'])+'</p>',
             '<div class="summary">'+escape(report['status'])+f" · {len(report['dependencies'])} dependencies · {len(report['findings'])} static findings · {report['usage']['requests']} requests</div>",
             '<p>Scope: '+escape(report['root'])+'</p>',
             '<section><h2>Local / GitHub</h2><pre>'+escape(json.dumps(report['github'], indent=2))+'</pre></section>',
             '<section><h2>Architecture</h2>'+architecture_svg(report['architecture'])+'</section>',
             '<section><h2>Dependencies</h2>'+table(['Package', 'Location', 'Declared', 'Exact version', 'Latest', 'Advisories'], [(d['name'],d['location'],d['declared'],d['version'] or 'unknown',d.get('latest') or 'unknown',d.get('vulnerability_status','UNKNOWN')) for d in report['dependencies']])+'</section>',
             '<section><h2>Duplicate candidates</h2>'+table(['Locations', 'Next step'], [(', '.join(g),'Review ownership and imports before moving code') for g in report['architecture']['duplicate_candidates']])+'</section>',
             '<section><h2>Static findings</h2>']
    for finding in report['findings']:
        parts.append('<article><h3>'+escape(finding['title'])+'</h3>'+table(['Field','Evidence'],[(key,value) for key,value in finding.items()])+'</article>')
    parts += ['</section><section><h2>Sources</h2>'+table(['Primary source','Checked','Status'],[(s['url'],s['checked_at'],s['status']) for s in report['sources']])+'</section>',
              '<section><h2>Upstream repository evidence</h2><pre>'+escape(json.dumps(report['upstream'],indent=2))+'</pre></section>',
              '<section><h2>Boundaries and usage</h2><pre>'+escape(json.dumps({'boundaries':report['boundaries'],'usage':report['usage'],'phases':report['agent_plan']},indent=2))+'</pre></section>',
              '<section><h2>Next actions</h2><ul>'+''.join('<li>'+escape(action)+'</li>' for action in report['next_actions'])+'</ul></section></html>']
    return '\n'.join(parts)
