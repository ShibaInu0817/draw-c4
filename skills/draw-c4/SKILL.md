---
name: draw-c4
description: Generate or update an interactive architecture diagram from a codebase — one self-contained HTML file with C4-style drill-down levels, pan and zoom, an inspector, and a step-through player for runtime flows. Use this whenever someone wants to see, draw, map, visualise or document how their code fits together — 'diagram my codebase', 'show me the architecture', 'how does a request flow through this', 'make me a C4 diagram', 'something like IcePanel or Structurizr', or asks to refresh an existing diagram after the code changed. Use it even when the word 'diagram' never appears; any request to map services, containers, components, data stores, queues, dependencies or request paths out of source code belongs here. Also use it when handed an existing architecture plot HTML and asked to change, extend, correct or re-generate it.
---

# draw-c4 — interactive C4 architecture diagrams

Turns a codebase into an explorable diagram: a single HTML file with no build step
and no dependencies, holding up to four levels of detail and a set of animated
runtime flows.

## Find the skill directory first

**Do this once, before any other step.** This skill's files sit wherever it was
installed, which is never the user's working directory. Resolve that location and
use absolute paths from then on — bare relative paths like `scripts/plot.py` will
not resolve:

```bash
SKILL="$(dirname "$(dirname "$(find "${CLAUDE_PLUGIN_ROOT:-/nonexistent}" \
  ~/.claude/skills ~/.agents/skills "$PWD/.claude/skills" \
  -name plot.py -path '*draw-c4*' 2>/dev/null | head -1)")")"
```

That covers every install route — plugin, `npx skills`, and a hand-copied skill
folder at user or project level. Sanity-check it resolved:

```bash
ls "$SKILL/scripts/plot.py" "$SKILL/assets/plot-template.html"
```

Every command below writes `"$SKILL"` for that directory. Keep the quotes; the
path can contain spaces. Read the bundled reference files by absolute path too —
`$SKILL/references/model-schema.md`, `$SKILL/assets/example-model.json`.

The model file and the output HTML are the user's, so those stay wherever the
user wants them, normally the repo being diagrammed. Never write into `$SKILL`.

Read `$SKILL/references/model-schema.md` for every field. Read
`$SKILL/assets/example-model.json` before writing a model — it is a complete,
hand-tuned example and imitating its level of specificity is most of the job.

## How the pieces fit

The output file is two things welded together:

- **The renderer** — `$SKILL/assets/plot-template.html`, about 700 lines of HTML, CSS and
  JS. It is fixed. It handles layout transforms, hit testing, the inspector, the
  flow player, keyboard shortcuts. Never edit it and never write it out by hand.
- **The model** — one JSON object describing the system: levels, nodes, edges,
  flows. This is the only thing that varies between diagrams, and it is the only
  thing to write.

`$SKILL/scripts/plot.py` moves the model in and out of the HTML. Because the model
round-trips exactly, an existing diagram can be read back, edited as data, and
rebuilt — which is what makes updating cheap.

## Workflow: a new diagram

1. **Read the code before writing anything.** See "Reading a codebase" below. Do
   not start from the README's architecture section alone; it is usually stale.
2. **Write the model** to `model.json`. Omit `x`/`y` — the layout step supplies
   them.
3. **Lay it out:** `python3 "$SKILL/scripts/plot.py" layout model.json --all`
4. **Check it:** `python3 "$SKILL/scripts/plot.py" check model.json` — clear every **error**
   before moving on. It catches the mistakes that are easy to make and
   invisible afterwards: an edge pointing at a node id that does not exist, a
   flow cue with no matching edge, a drill target that was renamed.
   **Warnings need judgement, not blind obedience.** A `jump` warning on an
   orchestrator that fans out is expected and correct — see "Keep the cues
   contiguous". Do not invent a hop that the code does not make just to silence
   `check`; a wrong diagram that validates cleanly is worse than a right one that
   warns. The shipped `$SKILL/assets/example-model.json` emits two such warnings by
   design.
5. **Tune the placement.** Auto-layout guarantees nothing overlaps; it does not
   guarantee the diagram reads well. Nudge coordinates so the shape of the
   picture matches the shape of the system — clients on the left, stores beside
   the service that owns them, the event bus spanning its consumers. Compare
   against `$SKILL/assets/example-model.json`, which is hand-placed. Re-run `check`
   after nudging.
6. **Build:** `python3 "$SKILL/scripts/plot.py" build model.json architecture.html`
7. Keep `model.json` next to the HTML and tell the user to keep it — it is the
   source, and the next update starts from it.

## Workflow: updating an existing diagram

1. `python3 "$SKILL/scripts/plot.py" extract architecture.html model.json` (skip if the
   model file was kept).
2. Re-read the parts of the code that changed. Diff mentally against the model:
   what is new, what is gone, what was renamed, what changed direction.
3. Edit the JSON. When something is deleted, delete its edges and any flow cues
   that used them too — `check` will otherwise report them, which is the point.
4. `python3 "$SKILL/scripts/plot.py" layout model.json` — with no `--all`, this keeps
   every existing coordinate and parks only the new parts in a spare column on
   the right. Move them into place deliberately; do not leave them stacked.
5. `check`, then `build`.

Preserving coordinates matters. A diagram someone has read a few times has a
shape they remember, and reshuffling it on every update destroys that.

## Reading a codebase

Everything in the diagram should be traceable to something in the repository.
Guessing produces a diagram that looks authoritative and is wrong, which is worse
than no diagram. If something is genuinely unclear, either leave it out or say so
plainly in the node's description.

**Level 1, context** — only worth drawing when there are real external actors and
third parties. Evidence: outbound HTTP base URLs, vendor SDKs in the dependency
manifest, webhook route handlers, env vars named after vendors, auth providers,
the roles in the authorisation code.

**Level 2, containers** — the things that deploy or run separately, plus the
stores they own. This is the level people actually want. Evidence: services in
`docker-compose.yml`, Kubernetes or Helm manifests, a `Procfile`, monorepo
packages that each have their own entry point or Dockerfile, deploy jobs in CI,
Terraform resources. Databases come from connection strings and migration
directories; queues and topics from producer and consumer configuration.

**Level 3, components** — the insides of one container, and only for the one or
two containers where the interesting logic lives. Evidence: module and package
structure, dependency-injection wiring, classes named `*Controller`, `*Service`,
`*Repository`, `*Client`, `*Handler`, `*Consumer`. Point at them with `drill` on
the container node.

Skip a level rather than padding it. A three-service system with no third parties
needs one level, not three.

### What earns a box

Something that runs, stores state, or is a boundary someone can cross. Not every
file, not every class, not every utility package. If removing it from the diagram
would not change how anyone reasons about the system, leave it out.

Aim for **5 to 15 nodes per level**. Past about eighteen it stops being a diagram
and becomes a haystack; that is the signal to push detail down into a `drill`
level instead.

### Writing the boxes

- `name` — what the code calls it. If the class is `SeatAllocator`, the box says
  Seat allocator, not "Allocation subsystem".
- `tech` — the real stack, plus the one operational fact that matters:
  `Redis · TTL 480s`, `gRPC · 400ms budget`, `Postgres · read replicas`. Read it
  off the config, do not invent it.
- `desc` — one or two sentences: what it is responsible for, and one thing that
  is true and not obvious from the name. The non-obvious half is what makes the
  diagram worth opening. "Owns orders" is filler. "The only thing allowed to say
  a seat is taken" is a fact someone can act on.
- `kind` — `person`, `client`, `focus`, `service`, `component`, `store`, `queue`,
  `external`. This drives the colour, so getting stores and queues right is what
  makes the picture legible at a glance.

### Drawing the lines

An arrow points from the **initiator to the thing it calls**, which is not always
the direction data moves. A service reading from a database still points at the
database.

Mark an edge `"kind": "async"` when nobody is waiting on the far end — events,
queue publishes, webhooks, scheduled exports. The renderer dashes these, and the
async/sync split is usually the most useful single distinction in the picture.

`label` should say what crosses the line, in the code's own words: the route, the
RPC method, the topic name, the SQL access pattern.

## Flows

Flows are the reason this beats a static diagram, so do not skip them. Each one
replays a real path through the system one hop at a time.

Find them by following a route handler through to its effects, by reading
integration or end-to-end tests, by reading an orchestrator or saga class, or by
tracing what a message consumer does. Two to four flows is right: the main happy
path, plus at least one that shows something going sideways — a timeout, an
expiry, a retry, a compensation.

Each cue names one edge that already exists at that level, plus:

- `title` — three or four words, the name of the step.
- `note` — a sentence or two on what happens and why. Put concrete values from
  the code in `<b>` tags: timeouts, status codes, topic names, TTLs, amounts.
  These specifics are what make a flow convincing.

A cue whose `from`/`to` pair is not an edge at that level will not animate, and
`check` reports it.

### Keep the cues contiguous

A flow is a path, so consecutive cues must connect: each cue should carry on from
where the last one ended — ideally `cue[n].from == cue[n-1].to`. When two
neighbouring cues share no node at all, the dot teleports across the canvas and
the story breaks. That gap almost always means a **real hop is missing** — most
often an async/event edge you left out because its arrow points the "wrong" way.
A change stream, a queue delivery, or a webhook is a hop: draw it source →
consumer (`mongo → generator`, `bus → consumer`) and give it its own cue, rather
than jumping from the writer's chain straight into the reader's chain. `check`
warns on any two consecutive cues that share no node.

The one accepted exception is an **orchestrator that fans out** — a worker or saga
that calls several collaborators in turn. There, successive cues legitimately
share only the orchestrator node (`worker → db`, then `worker → provider`): the
return to the orchestrator between calls is understood. Keep those cues adjacent
so the hub is obvious, and fold a pure leaf round-trip (a call out to a
provider/store and straight back) into the note of the orchestrator's cue instead
of spending a cue on an edge the flow immediately has to teleport back from.

### Give an orchestrator its own level and flow

A node whose whole job is *sequence* — a Temporal workflow, a saga, a pipeline —
cannot be explained by its `desc` alone; a box can't hold an ordering. When you
`drill` into one, add a flow **at that component level** that steps through its
activities in order (drain/receive → validate → call → persist → publish), and
put the operational facts that make it real in the cues and the node text:
retry counts, timeouts, the dedup/idempotency key, the wait condition,
continue-as-new. If the workflow node only says what it *is* and never what it
*does step by step*, the most important part of the system is missing.

## Commands

```bash
python3 "$SKILL/scripts/plot.py" build   model.json diagram.html   # model -> HTML
python3 "$SKILL/scripts/plot.py" extract diagram.html model.json   # HTML -> model
python3 "$SKILL/scripts/plot.py" check   model.json                # validate; exits 1 on error
python3 "$SKILL/scripts/plot.py" layout  model.json [--level ID] [--all]
python3 "$SKILL/scripts/plot.py" stats   model.json                # what's in there
```

`build` refuses to run when `check` finds errors. `--force` overrides, but a
diagram with a dangling reference has a dead flow or a dead drill-down in it, so
fix the model instead.

`layout` without `--all` only places nodes that have no coordinates yet.

## Delivering it

Save the HTML and `model.json` to the output directory and present both. Tell the
user, briefly: the interactions available (drill down, hover to trace, flow
player, search), and that `model.json` is the source to keep for next time.

Do not paste the model JSON into the reply — it is long and the file is right
there.
