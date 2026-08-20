#!/usr/bin/env python3
"""Dependency-free, append-only local lesson store."""

import argparse, hashlib, json, os, re, secrets, sys
from datetime import datetime, timezone
from pathlib import Path

TOKEN_RE = re.compile(r"[a-z0-9_./:+-]{2,}", re.I)
SECRET_RE = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+|(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{12,})", re.I)
MAX_LESSONS, TARGET_LESSONS, MAX_BYTES = 100, 80, 512 * 1024

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def path_for(a): return Path(a.store).expanduser().resolve() if a.store else Path(a.root).expanduser().resolve() / ".agent-memory" / "lessons.jsonl"

def clean(value, field, limit=1200):
    value = " ".join(value.strip().split())
    if not value: raise ValueError(f"{field} must not be empty")
    if len(value) > limit: raise ValueError(f"{field} exceeds {limit} characters")
    if SECRET_RE.search(value): raise ValueError(f"{field} appears to contain a secret; redact it")
    return value

def append(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try: os.write(fd, data); os.fsync(fd)
    finally: os.close(fd)

def load(path):
    events, warnings = [], []
    if not path.exists(): return events, warnings
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        try:
            value = json.loads(line)
            if isinstance(value, dict): events.append(value)
            else: warnings.append(f"line {number}: event is not an object")
        except json.JSONDecodeError as exc: warnings.append(f"line {number}: invalid JSON ({exc.msg})")
    return events, warnings

def state(events):
    lessons, feedback = {}, {}
    for event in events:
        if event.get("event") == "lesson" and event.get("id"): lessons[event["id"]] = event
        elif event.get("event") == "feedback" and event.get("lesson_id"): feedback.setdefault(event["lesson_id"], []).append(event)
    return lessons, feedback

def confidence(lesson, feedback):
    score = 0.65 if lesson.get("status") == "verified" else 0.35
    for item in feedback: score += 0.08 if item.get("result") == "success" else -0.22
    return max(0.0, min(1.0, score))

def compact_store(path, force=False):
    events, warnings = load(path); lessons, feedback_map = state(events)
    if not force and len(lessons) < MAX_LESSONS and (not path.exists() or path.stat().st_size < MAX_BYTES): return 0, warnings
    ranked = sorted(lessons.values(), key=lambda lesson:(confidence(lesson,feedback_map.get(lesson["id"],[])), lesson.get("status")=="verified", lesson.get("created_at","")), reverse=True)
    kept = ranked[:TARGET_LESSONS]; kept_ids={x["id"] for x in kept}; output=[]
    for event in events:
        if event.get("event")=="lesson" and event.get("id") in kept_ids: output.append(event)
        elif event.get("event")=="feedback" and event.get("lesson_id") in kept_ids: output.append(event)
    path.parent.mkdir(parents=True,exist_ok=True); temp=path.with_suffix(path.suffix+".tmp")
    with temp.open("w",encoding="utf-8",newline="\n") as handle:
        for event in output: handle.write(json.dumps(event,ensure_ascii=False,sort_keys=True)+"\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temp,path); return len(lessons)-len(kept), warnings

def record(a):
    compact_store(path_for(a))
    fields = {key: clean(getattr(a, key), key) for key in ("problem", "cause", "action", "evidence")}
    tags = sorted({clean(tag, "tag", 80).lower() for tag in a.tags.split(",") if tag.strip()})
    digest = hashlib.sha256((fields["problem"] + fields["cause"] + fields["action"]).encode()).hexdigest()[:10]
    event = {"event":"lesson", "id":f"l-{digest}-{secrets.token_hex(2)}", "created_at":now(), "scope":clean(a.scope,"scope",200), "status":a.status, "tags":tags, **fields}
    append(path_for(a), event); print(json.dumps({"stored":True,"id":event["id"],"path":str(path_for(a))})); return 0

def feedback(a):
    lessons, _ = state(load(path_for(a))[0])
    if a.id not in lessons: print(f"unknown lesson id: {a.id}", file=sys.stderr); return 2
    append(path_for(a), {"event":"feedback","lesson_id":a.id,"created_at":now(),"result":a.result,"evidence":clean(a.evidence,"evidence")})
    print(json.dumps({"stored":True,"lesson_id":a.id,"result":a.result})); return 0

def recall(a):
    events, warnings = load(path_for(a)); lessons, feedback_map = state(events); query = set(TOKEN_RE.findall(a.query.lower())); ranked=[]
    for lesson in lessons.values():
        text = " ".join(str(lesson.get(k,"")) for k in ("problem","cause","action","scope")) + " " + " ".join(lesson.get("tags",[]))
        overlap = len(query & set(TOKEN_RE.findall(text.lower())))
        if not overlap: continue
        conf = confidence(lesson, feedback_map.get(lesson["id"],[])); ranked.append((overlap/max(1,len(query))+conf*.2, conf, lesson))
    ranked.sort(key=lambda x:(x[0],x[1],x[2].get("created_at","")), reverse=True); matches=[]
    for score, conf, lesson in ranked[:a.limit]:
        fb=feedback_map.get(lesson["id"],[]); matches.append({**lesson,"confidence":round(conf,2),"score":round(score,3),"feedback":{"success":sum(x.get("result")=="success" for x in fb),"failure":sum(x.get("result")=="failure" for x in fb)}})
    print(json.dumps({"path":str(path_for(a)),"query":a.query,"matches":matches,"warnings":warnings},ensure_ascii=False,indent=2)); return 0

def validate(a):
    events, warnings=load(path_for(a)); ids={e.get("id") for e in events if e.get("event")=="lesson"}; errors=list(warnings)
    required={"id","created_at","scope","problem","cause","action","evidence","tags","status"}
    for number,event in enumerate(events,1):
        if event.get("event")=="lesson":
            missing=required-event.keys()
            if missing: errors.append(f"line {number}: missing {', '.join(sorted(missing))}")
            if event.get("status") not in {"candidate","verified"}: errors.append(f"line {number}: invalid status")
        elif event.get("event")=="feedback":
            if event.get("result") not in {"success","failure"}: errors.append(f"line {number}: invalid result")
            if event.get("lesson_id") not in ids: errors.append(f"line {number}: unknown lesson reference")
        else: errors.append(f"line {number}: unknown event type")
    print(json.dumps({"path":str(path_for(a)),"valid":not errors,"events":len(events),"errors":errors},indent=2)); return 0 if not errors else 1

def stats(a):
    path=path_for(a); events,warnings=load(path); lessons,fb=state(events); size=path.stat().st_size if path.exists() else 0; print(json.dumps({"path":str(path),"lessons":len(lessons),"lesson_limit":MAX_LESSONS,"bytes":size,"byte_limit":MAX_BYTES,"feedback":sum(map(len,fb.values())),"verified":sum(x.get("status")=="verified" for x in lessons.values()),"warnings":warnings},indent=2)); return 0

def compact(a):
    removed,warnings=compact_store(path_for(a),force=True); print(json.dumps({"path":str(path_for(a)),"removed":removed,"warnings":warnings},indent=2)); return 0

def build_parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
    def common(x): x.add_argument("--root",default="."); x.add_argument("--store")
    x=sub.add_parser("recall"); common(x); x.add_argument("--query",required=True); x.add_argument("--limit",type=int,default=5); x.set_defaults(func=recall)
    x=sub.add_parser("record"); common(x)
    for key in ("problem","cause","action","evidence"): x.add_argument(f"--{key}",required=True)
    x.add_argument("--tags",default=""); x.add_argument("--scope",default="project"); x.add_argument("--status",choices=("candidate","verified"),default="candidate"); x.set_defaults(func=record)
    x=sub.add_parser("feedback"); common(x); x.add_argument("--id",required=True); x.add_argument("--result",choices=("success","failure"),required=True); x.add_argument("--evidence",required=True); x.set_defaults(func=feedback)
    x=sub.add_parser("validate"); common(x); x.set_defaults(func=validate)
    x=sub.add_parser("stats"); common(x); x.set_defaults(func=stats)
    x=sub.add_parser("compact"); common(x); x.set_defaults(func=compact); return p

if __name__ == "__main__":
    try:
        args=build_parser().parse_args(); raise SystemExit(args.func(args))
    except ValueError as exc: print(f"error: {exc}",file=sys.stderr); raise SystemExit(2)
