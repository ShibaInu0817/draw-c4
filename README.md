# draw-c4

A [Claude Code](https://code.claude.com) **Skill** (packaged as an installable plugin) that turns a
codebase into an **interactive, C4-style architecture diagram** — a single self-contained HTML file
with no build step and no dependencies.

The output has:

- **C4-style drill-down levels** — context → containers → components, up to four levels of detail
- **Pan & zoom** across the canvas
- **An inspector** for nodes and edges
- **A step-through player** that animates runtime flows (how a request moves through the system)

Everything lives in one HTML file you can open in any browser, commit, or share.

---

## Before you publish (repo owner checklist)

This repo ships with placeholders. Replace them before you push it public:

1. `TODO-AUTHOR` → your name or GitHub handle, in:
   - [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) (`owner.name`)
   - [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) (`author.name`)
   - [`LICENSE`](LICENSE) (copyright line)
2. `<github-owner>` → your GitHub owner/repo in the install command below.

---

## Install

### As a plugin (recommended)

In a Claude Code session:

```
/plugin marketplace add <github-owner>/draw-c4
/plugin install draw-c4@tee-plugins
```

The skill loads automatically and Claude invokes it whenever you ask it to diagram, map, or visualise
a codebase.

### Manually (no plugin)

Copy the skill folder into your skills directory:

```bash
# user-level (available in every project)
cp -R skills/draw-c4 ~/.claude/skills/

# or project-level
cp -R skills/draw-c4 /path/to/your/project/.claude/skills/
```

---

## Requirements

- **Python 3** — standard library only (`argparse`, `json`, `os`, `re`, `sys`). No `pip install` needed.

---

## How it works

The diagram is two things welded into one HTML file:

- **The renderer** — [`skills/draw-c4/assets/plot-template.html`](skills/draw-c4/assets/plot-template.html),
  fixed HTML/CSS/JS that handles layout, hit-testing, the inspector, and the flow player.
- **The model** — one JSON object describing the system (levels, nodes, edges, flows). This is the only
  thing that varies between diagrams.

[`skills/draw-c4/scripts/plot.py`](skills/draw-c4/scripts/plot.py) moves the model in and out of the HTML,
so an existing diagram can be read back, edited as data, and rebuilt:

```bash
cd skills/draw-c4

# build a new diagram from a model
python3 scripts/plot.py layout model.json --all      # auto-place nodes
python3 scripts/plot.py check  model.json            # validate the model
python3 scripts/plot.py build  model.json architecture.html

# update an existing diagram
python3 scripts/plot.py extract architecture.html model.json   # recover the model
# ...edit model.json...
python3 scripts/plot.py layout model.json            # keep coords, park new nodes
python3 scripts/plot.py check  model.json
python3 scripts/plot.py build  model.json architecture.html
```

- [`skills/draw-c4/references/model-schema.md`](skills/draw-c4/references/model-schema.md) documents every
  model field.
- [`skills/draw-c4/assets/example-model.json`](skills/draw-c4/assets/example-model.json) is a complete,
  hand-tuned example to imitate.

Full authoring guidance lives in the skill itself:
[`skills/draw-c4/SKILL.md`](skills/draw-c4/SKILL.md).

---

## License

[MIT](LICENSE).
