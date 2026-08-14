# Model schema

Every diagram is one JSON object. `assets/example-model.json` is a complete
worked instance of everything below.

- [Top level](#top-level)
- [Level](#level)
- [Node](#node)
- [Edge](#edge)
- [Flow](#flow)
- [Cue](#cue)
- [Kinds](#kinds)
- [Coordinates](#coordinates)
- [Worked fragment](#worked-fragment)

## Top level

```json
{
  "name": "Encore",
  "tagline": "live event ticketing",
  "entry": "containers",
  "levels": { "<level-id>": { } },
  "flows": [ ]
}
```

| field | required | notes |
|---|---|---|
| `name` | yes | Shown in the header and the browser tab. The system's name. |
| `tagline` | no | Small text beside the name. What the system is, in three or four words. |
| `entry` | no | Which level opens first. Defaults to the first key in `levels`. Usually the container level — it is where people want to land, even when a context level exists above it. |
| `levels` | yes | Object keyed by level id. Ids are free-form; `containers` and `orders.components` are the convention used here. |
| `flows` | no | Array. Omitting it loses the best part of the format. |

Do not add a `kinds` key. Colours belong to the renderer, so that every diagram
built this way reads the same.

## Level

```json
{
  "id": "containers",
  "name": "Containers",
  "label": "Inside Encore Ticketing",
  "parent": "context",
  "blurb": "The deployable pieces and the stores they own.",
  "canvas": { "w": 1560, "h": 960 },
  "nodes": [ ],
  "edges": [ ]
}
```

| field | required | notes |
|---|---|---|
| `id` | yes | Must match the key it is stored under. |
| `name` | yes | Short, for the breadcrumb. One or two words. |
| `label` | yes | The heading in the inspector when nothing is selected. |
| `parent` | no | Level id one step up. Drives the breadcrumb and the Esc key. Omit on the top level. |
| `blurb` | no | A sentence orienting someone who just arrived. Worth writing. |
| `canvas` | yes | Bounding box used to fit the view. `plot.py layout` sets it; do not maintain it by hand. |
| `nodes` | yes | At least one. |
| `edges` | yes | May be empty, but a level with no edges is rarely worth drawing. |

## Node

```json
{
  "id": "inventory",
  "name": "Seat inventory",
  "kind": "service",
  "tech": "Rust",
  "x": 620,
  "y": 220,
  "desc": "The only thing allowed to say a seat is taken.",
  "drill": "inventory.components",
  "w": 210,
  "h": 78
}
```

| field | required | notes |
|---|---|---|
| `id` | yes | Unique within its level. Edges and cues reference it. Reused across levels freely — `bus` at one level and `x-bus` at another are separate nodes. |
| `name` | yes | Keep under about 22 characters or it will crowd the box. |
| `kind` | yes | See [Kinds](#kinds). |
| `tech` | yes | Stack plus one operational fact. Use `·` as the separator. |
| `x`, `y` | yes at build time | Top-left corner. Supplied by `plot.py layout`. |
| `desc` | yes in practice | Inspector text. `check` warns when it is missing. |
| `drill` | no | Level id to open on double-click. The node gets an `⤢ open` marker. |
| `w`, `h` | no | Default 210 × 78. Widen for a node that spans several others, like an event bus (`"w": 540, "h": 70`). |

Nodes that live outside the current boundary but need to be shown for context —
another container seen from inside a component level — get `kind: "external"` and
an id prefixed `x-` by convention.

## Edge

```json
{ "from": "orders", "to": "bus", "label": "order.paid", "kind": "async" }
```

| field | required | notes |
|---|---|---|
| `from`, `to` | yes | Node ids **in the same level**. A reference to a node in another level is the most common way to break a model; `check` catches it. |
| `label` | no | What crosses the line. Shown on hover, during a matching cue, and when "Label every line" is on. |
| `kind` | no | `"async"` dashes the line. Use it for events, queue publishes, webhooks, scheduled jobs — anything where the caller does not wait. |

Direction is caller → callee, not the direction data travels.

Two nodes may have more than one edge between them, but a flow cue identifies its
edge only by the `from`/`to` pair, so a duplicated pair makes cues ambiguous.
Prefer one edge with a combined label.

## Flow

```json
{
  "id": "buy",
  "name": "Buy a ticket",
  "level": "containers",
  "meta": "11 cues · happy path",
  "cues": [ ]
}
```

| field | required | notes |
|---|---|---|
| `id` | yes | Unique across flows. |
| `name` | yes | Shown in the left rail. Name the outcome, not the mechanism: "Buy a ticket", not "POST /orders handler". |
| `level` | yes | Selecting the flow switches to this level. |
| `meta` | no | Grey line under the name. `"<n> cues · <character>"` reads well. |
| `cues` | yes | Ordered. Three to twelve is the useful range. |

## Cue

```json
{
  "from": "orders",
  "to": "inventory",
  "title": "Confirm the hold",
  "note": "The saga asks inventory to promote the hold. <b>400ms budget</b> — a timeout is treated as a no."
}
```

| field | required | notes |
|---|---|---|
| `from`, `to` | yes | Must match an existing edge at the flow's level, exactly and in that direction. |
| `title` | yes | Three or four words. Appears in the cue strip, so it must survive truncation. |
| `note` | yes | One or two sentences. `<b>` is the only markup used; wrap concrete values from the code in it. |

Cues are what the flow player animates: the edge lights amber, a dot travels
along it, and the note appears in the cue sheet.

Cues must **chain**: a flow is a path, so each cue should continue from the last
— ideally `cue[n].from == cue[n-1].to`, and at minimum the two must share a node.
Two consecutive cues that share no node make the dot teleport, and `check` warns.
The gap usually means a real hop is missing — often an async event edge (a change
stream, a queue delivery) drawn source → consumer. The accepted exception is an
orchestrator hub whose successive cues share only the orchestrator node.

## Kinds

| kind | colour | use for |
|---|---|---|
| `person` | rose | Human roles. Context level only. |
| `client` | amber | Things a person operates: web app, mobile app, CLI. |
| `focus` | amber, filled | The system under discussion on a context diagram. Usually exactly one, with `drill` set. |
| `service` | white | Something that runs. The default. |
| `component` | white | A part inside a container. Component levels only. |
| `store` | teal | Databases, caches, object storage, search indexes. |
| `queue` | lavender, filled | Brokers, topics, streams. |
| `external` | grey, dashed | Third parties, and anything across the boundary being drawn. |

An unknown kind falls back to `service` and `check` warns.

## Coordinates

The origin is top-left and units are pixels at 100% zoom. `x`/`y` is the node's
top-left corner. There is no grid to snap to, but leaving a 12px gap between
boxes is enforced by `check`'s overlap test.

Practical placement, once `layout` has produced something valid:

- Direction of flow left to right — clients on the left, third parties on the right.
- A store sits immediately right of the service that owns it, on the same row.
- An event bus is wide and low, under its publishers and above its consumers.
- Leave a visible gutter between groups that mean different things. The empty
  space carries information.

## Worked fragment

A minimal two-node level with one flow, complete and valid:

```json
{
  "name": "Pipeline",
  "levels": {
    "containers": {
      "id": "containers",
      "name": "Containers",
      "label": "Inside the pipeline",
      "canvas": { "w": 700, "h": 260 },
      "nodes": [
        { "id": "api", "name": "Ingest API", "kind": "service",
          "tech": "FastAPI · uvicorn", "x": 60, "y": 90,
          "desc": "Accepts uploads and writes them straight to object storage." },
        { "id": "s3", "name": "Raw bucket", "kind": "store",
          "tech": "S3 · lifecycle 30d", "x": 400, "y": 90,
          "desc": "Write-once landing zone. Nothing downstream reads it twice." }
      ],
      "edges": [
        { "from": "api", "to": "s3", "label": "PutObject" }
      ]
    }
  },
  "flows": [
    {
      "id": "upload", "name": "Upload a file", "level": "containers",
      "meta": "1 cue · happy path",
      "cues": [
        { "from": "api", "to": "s3", "title": "Landed",
          "note": "Streamed straight through, never buffered to disk. Keyed by <b>sha256</b> so a re-upload is a no-op." }
      ]
    }
  ]
}
```
