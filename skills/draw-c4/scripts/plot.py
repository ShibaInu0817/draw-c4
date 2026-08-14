#!/usr/bin/env python3
"""
plot.py — build, inspect and repair interactive architecture diagrams.

The diagram is one self-contained HTML file. All of the variable content lives
in a single JSON object called the *model*; the rest of the file is a fixed
renderer. These commands move a model in and out of that file so you never have
to hand-edit the renderer.

    plot.py build    model.json diagram.html   # model -> standalone HTML
    plot.py extract  diagram.html model.json   # HTML  -> model (for updating)
    plot.py check    model.json                # find broken references, overlaps
    plot.py layout   model.json                # assign x/y to nodes that lack them
    plot.py stats    model.json                # quick summary of what's in there

Typical first run:   layout -> check -> build
Typical update:      extract -> edit json -> layout -> check -> build
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.join(HERE, '..', 'assets', 'plot-template.html')

START = '/* @@MODEL_START@@'
END = '/* @@MODEL_END@@ */'

NODE_W, NODE_H = 210, 78
GAP_X, GAP_Y = 90, 46
MARGIN = 60

VALID_KINDS = {'person', 'client', 'focus', 'service',
               'component', 'store', 'queue', 'external'}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def load_model(path):
    if not os.path.exists(path):
        die(f"no model at {path}")
    with open(path) as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            die(f"{path} is not valid JSON: {exc}")


def save_model(model, path):
    with open(path, 'w') as fh:
        json.dump(model, fh, indent=2, ensure_ascii=False)
        fh.write('\n')


def size(node):
    return node.get('w', NODE_W), node.get('h', NODE_H)


def levels_of(model):
    return model.get('levels', {})


# --------------------------------------------------------------------------
# build / extract
# --------------------------------------------------------------------------
def cmd_build(args):
    model = load_model(args.model)
    template_path = args.template or DEFAULT_TEMPLATE
    if not os.path.exists(template_path):
        die(f"no template at {template_path}")

    with open(template_path) as fh:
        html = fh.read()

    if START not in html or END not in html:
        die("template is missing its @@MODEL_START@@ / @@MODEL_END@@ markers")

    problems = validate(model)
    fatal = [p for p in problems if p[0] == 'error']
    if fatal and not args.force:
        for kind, msg in problems:
            print(f"  {kind}: {msg}")
        die(f"{len(fatal)} blocking problem(s). Fix them, or pass --force.")

    head = html[:html.index(START)]
    tail = html[html.index(END) + len(END):]
    payload = json.dumps(model, ensure_ascii=False, separators=(',', ':'))
    block = (f"{START}  ——  written by scripts/plot.py, do not hand-edit this block */\n"
             f"const MODEL = {payload};\n{END}")

    out = head + block + tail
    with open(args.out, 'w') as fh:
        fh.write(out)

    n_nodes = sum(len(L.get('nodes', [])) for L in levels_of(model).values())
    print(f"built {args.out}  ({len(out) // 1024} KB, "
          f"{len(levels_of(model))} levels, {n_nodes} parts, "
          f"{len(model.get('flows', []))} flows)")
    for kind, msg in problems:
        if kind == 'warn':
            print(f"  warn: {msg}")


def cmd_extract(args):
    if not os.path.exists(args.html):
        die(f"no file at {args.html}")
    with open(args.html) as fh:
        html = fh.read()
    if START not in html or END not in html:
        die(f"{args.html} has no model block — was it built by plot.py?")

    body = html[html.index(START):html.index(END)]
    match = re.search(r'const MODEL\s*=\s*(\{.*\});?\s*$', body, re.S)
    if not match:
        die("could not find the model assignment inside the block")
    try:
        model = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        die(f"model block is not valid JSON: {exc}")

    save_model(model, args.model)
    print(f"extracted model to {args.model}")


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def validate(model):
    """Return a list of (severity, message). 'error' blocks a build."""
    out = []
    levels = levels_of(model)
    if not levels:
        out.append(('error', 'model has no levels'))
        return out

    if model.get('entry') and model['entry'] not in levels:
        out.append(('error', f"entry level '{model['entry']}' does not exist"))

    for lid, L in levels.items():
        nodes = L.get('nodes', [])
        edges = L.get('edges', [])
        if not nodes:
            out.append(('error', f"[{lid}] has no nodes"))
            continue
        for field in ('name', 'label', 'canvas'):
            if field not in L:
                out.append(('warn', f"[{lid}] is missing '{field}'"))

        ids = {}
        for n in nodes:
            if 'id' not in n:
                out.append(('error', f"[{lid}] a node has no id"))
                continue
            if n['id'] in ids:
                out.append(('error', f"[{lid}] duplicate node id '{n['id']}'"))
            ids[n['id']] = n
            if n.get('kind') not in VALID_KINDS:
                out.append(('warn', f"[{lid}] {n['id']}: unknown kind "
                                    f"'{n.get('kind')}' — falls back to service"))
            if 'x' not in n or 'y' not in n:
                out.append(('error', f"[{lid}] {n['id']} has no position — run layout"))
            if not n.get('desc'):
                out.append(('warn', f"[{lid}] {n['id']} has no description"))
            drill = n.get('drill')
            if drill and drill not in levels:
                out.append(('error', f"[{lid}] {n['id']} drills into "
                                     f"missing level '{drill}'"))

        for e in edges:
            for side in ('from', 'to'):
                if e.get(side) not in ids:
                    out.append(('error', f"[{lid}] edge references unknown node "
                                         f"'{e.get(side)}'"))
            if e.get('from') == e.get('to'):
                out.append(('warn', f"[{lid}] self-edge on '{e.get('from')}'"))

        parent = L.get('parent')
        if parent and parent not in levels:
            out.append(('error', f"[{lid}] parent level '{parent}' does not exist"))

        # geometry
        placed = [n for n in nodes if 'x' in n and 'y' in n]
        for i, a in enumerate(placed):
            aw, ah = size(a)
            for b in placed[i + 1:]:
                bw, bh = size(b)
                if (a['x'] < b['x'] + bw + 12 and b['x'] < a['x'] + aw + 12 and
                        a['y'] < b['y'] + bh + 12 and b['y'] < a['y'] + ah + 12):
                    out.append(('warn', f"[{lid}] {a['id']} and {b['id']} overlap"))
        canvas = L.get('canvas') or {}
        for n in placed:
            nw, nh = size(n)
            if canvas and (n['x'] + nw > canvas.get('w', 0) or
                           n['y'] + nh > canvas.get('h', 0)):
                out.append(('warn', f"[{lid}] {n['id']} sits outside the canvas — "
                                    f"run layout to resize"))

    for f in model.get('flows', []):
        lid = f.get('level')
        L = levels.get(lid)
        if not L:
            out.append(('error', f"flow '{f.get('id')}' targets missing level '{lid}'"))
            continue
        pairs = {(e.get('from'), e.get('to')) for e in L.get('edges', [])}
        cues = f.get('cues', [])
        for i, cue in enumerate(cues, 1):
            if (cue.get('from'), cue.get('to')) not in pairs:
                out.append(('error', f"flow '{f.get('id')}' cue {i} "
                                     f"({cue.get('from')} -> {cue.get('to')}) "
                                     f"has no matching edge in [{lid}]"))
            if not cue.get('note'):
                out.append(('warn', f"flow '{f.get('id')}' cue {i} has no note"))
        # contiguity: consecutive cues must share a node, or the dot teleports.
        for i in range(1, len(cues)):
            prev, cur = cues[i - 1], cues[i]
            if {prev.get('from'), prev.get('to')}.isdisjoint(
                    {cur.get('from'), cur.get('to')}):
                out.append(('warn', f"flow '{f.get('id')}' cues {i}->{i + 1} jump: "
                                    f"({prev.get('from')} -> {prev.get('to')}) then "
                                    f"({cur.get('from')} -> {cur.get('to')}) share no "
                                    f"node — insert the missing hop"))
    return out


def cmd_check(args):
    model = load_model(args.model)
    problems = validate(model)
    errors = [m for s, m in problems if s == 'error']
    warns = [m for s, m in problems if s == 'warn']
    for m in errors:
        print(f"  error: {m}")
    for m in warns:
        print(f"  warn:  {m}")
    if not problems:
        print("clean — every reference resolves and nothing overlaps")
    else:
        print(f"\n{len(errors)} error(s), {len(warns)} warning(s)")
    sys.exit(1 if errors else 0)


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------
def layered_positions(nodes, edges):
    """Sugiyama-lite: rank by longest path, order by barycentre, then stack."""
    ids = [n['id'] for n in nodes]
    index = {i: k for k, i in enumerate(ids)}
    succ = {i: [] for i in ids}
    pred = {i: [] for i in ids}
    for e in edges:
        a, b = e.get('from'), e.get('to')
        if a in succ and b in succ and a != b:
            succ[a].append(b)
            pred[b].append(a)

    # longest-path ranking, relaxed a bounded number of times so cycles terminate
    rank = {i: 0 for i in ids}
    for _ in range(len(ids)):
        changed = False
        for a in ids:
            for b in succ[a]:
                if rank[b] < rank[a] + 1 and rank[a] + 1 < len(ids):
                    rank[b] = rank[a] + 1
                    changed = True
        if not changed:
            break

    layers = {}
    for i in ids:
        layers.setdefault(rank[i], []).append(i)
    for r in layers:
        layers[r].sort(key=lambda i: index[i])

    # barycentre sweeps to cut down crossings
    order = {i: k for r in layers for k, i in enumerate(layers[r])}
    for sweep in range(6):
        keys = sorted(layers) if sweep % 2 == 0 else sorted(layers, reverse=True)
        for r in keys:
            neigh = pred if sweep % 2 == 0 else succ
            def bary(i):
                ns = [order[x] for x in neigh[i] if x in order]
                return sum(ns) / len(ns) if ns else order[i]
            layers[r].sort(key=bary)
            for k, i in enumerate(layers[r]):
                order[i] = k
    return layers


def layout_level(L, force_all):
    nodes = L.get('nodes', [])
    edges = L.get('edges', [])
    if not nodes:
        return 0

    todo = nodes if force_all else [n for n in nodes if 'x' not in n or 'y' not in n]
    if not todo:
        resize_canvas(L)
        return 0

    if force_all:
        by_id = {n['id']: n for n in nodes}
        layers = layered_positions(nodes, edges)
        col_x = MARGIN
        col_height = {}
        for r in sorted(layers):
            col = [by_id[i] for i in layers[r]]
            col_w = max(size(n)[0] for n in col)
            col_height[r] = sum(size(n)[1] for n in col) + GAP_Y * (len(col) - 1)
            y = MARGIN
            for node in col:
                nw, nh = size(node)
                node['x'] = col_x + (col_w - nw) // 2
                node['y'] = y
                y += nh + GAP_Y
            col_x += col_w + GAP_X
        # centre every column against the tallest one
        tallest = max(col_height.values()) if col_height else 0
        for r, height in col_height.items():
            shift = (tallest - height) // 2
            for nid in layers[r]:
                by_id[nid]['y'] += shift
        placed = len(nodes)
    else:
        # park newcomers in a fresh column to the right of everything else
        settled = [n for n in nodes if 'x' in n and 'y' in n]
        right = max((n['x'] + size(n)[0] for n in settled), default=MARGIN - GAP_X)
        top = min((n['y'] for n in settled), default=MARGIN)
        x = right + GAP_X
        y = top
        for node in todo:
            node['x'] = x
            node['y'] = y
            y += size(node)[1] + GAP_Y
        placed = len(todo)

    resize_canvas(L)
    return placed


def resize_canvas(L):
    nodes = [n for n in L.get('nodes', []) if 'x' in n and 'y' in n]
    if not nodes:
        return
    w = max(n['x'] + size(n)[0] for n in nodes) + MARGIN
    h = max(n['y'] + size(n)[1] for n in nodes) + MARGIN
    L['canvas'] = {'w': int(w), 'h': int(h)}


def cmd_layout(args):
    model = load_model(args.model)
    levels = levels_of(model)
    targets = [args.level] if args.level else list(levels)
    total = 0
    for lid in targets:
        if lid not in levels:
            die(f"no level called '{lid}'")
        moved = layout_level(levels[lid], args.all)
        total += moved
        c = levels[lid].get('canvas', {})
        print(f"  [{lid}] placed {moved} part(s), canvas "
              f"{c.get('w')}x{c.get('h')}")
    save_model(model, args.model)
    print(f"positioned {total} part(s) in {args.model}"
          f"{'' if args.all else '  (existing positions kept — use --all to redo)'}")


# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
def cmd_stats(args):
    model = load_model(args.model)
    print(f"{model.get('name', 'untitled')} — {model.get('tagline', '')}")
    for lid, L in levels_of(model).items():
        nodes = L.get('nodes', [])
        edges = L.get('edges', [])
        drills = [n['id'] for n in nodes if n.get('drill')]
        kinds = {}
        for n in nodes:
            kinds[n.get('kind', '?')] = kinds.get(n.get('kind', '?'), 0) + 1
        print(f"\n  [{lid}] {L.get('label', '')}")
        print(f"    parent: {L.get('parent') or '—'}   "
              f"parts: {len(nodes)}   lines: {len(edges)}   "
              f"async: {sum(1 for e in edges if e.get('kind') == 'async')}")
        print(f"    kinds: " + ', '.join(f"{k}×{v}" for k, v in sorted(kinds.items())))
        if drills:
            print(f"    opens into: {', '.join(drills)}")
    if model.get('flows'):
        print()
        for f in model['flows']:
            print(f"  flow '{f['id']}' on [{f.get('level')}] — "
                  f"{len(f.get('cues', []))} cues — {f.get('name')}")


# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)

    b = sub.add_parser('build', help='model JSON -> standalone HTML')
    b.add_argument('model')
    b.add_argument('out')
    b.add_argument('--template', help='override the bundled template')
    b.add_argument('--force', action='store_true', help='build despite errors')
    b.set_defaults(fn=cmd_build)

    e = sub.add_parser('extract', help='pull the model back out of a built HTML')
    e.add_argument('html')
    e.add_argument('model')
    e.set_defaults(fn=cmd_extract)

    c = sub.add_parser('check', help='validate references and geometry')
    c.add_argument('model')
    c.set_defaults(fn=cmd_check)

    l = sub.add_parser('layout', help='assign coordinates')
    l.add_argument('model')
    l.add_argument('--level', help='one level only (default: all)')
    l.add_argument('--all', action='store_true',
                   help='re-place every node, discarding current coordinates')
    l.set_defaults(fn=cmd_layout)

    s = sub.add_parser('stats', help='summarise a model')
    s.add_argument('model')
    s.set_defaults(fn=cmd_stats)

    args = p.parse_args()
    args.fn(args)


if __name__ == '__main__':
    main()
