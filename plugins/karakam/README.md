# karakam

Hacivat & Karagöz: an autonomous plan-and-build pair for Claude Code. `hacivat` turns a large job into a plan hardened by a four-lens critic panel; `karagoz` executes it in a `/loop`, handing each step to a Worker sub-agent and having adversarial Observers audit it. Both run only when you name them.

Full documentation, in English and Turkish: <https://github.com/azizi2407/karakam>.

## Install

```
/plugin install karakam --marketplace azizi2407/karakam
```

On older Claude Code: `/plugin marketplace add azizi2407/karakam`, then `/plugin install karakam@kara-skills`.

## What's inside

- **Skills:** `hacivat` (planning) and `karagoz` (execution).
- **Agents:** `worker-low`, `worker-medium`, `worker-high` (Sonnet), `worker-opus-high`, `worker-opus-xhigh` (refactor rounds), `observer-medium`, `observer-high`, `critic`. The skills spawn them by name; they aren't meant for other work.
- **One hooks module** (`hooks/progress.tsx`), described below.
- **No MCP servers and no credentials.** The plugin reads no keys or tokens and calls no outside service. The only model call of its own is the stop guard's, through your session's own client (below). Sub-agents use the MCP servers you have connected, under your own permission rules.

## What the hooks do

**Progress pane.** Shows the running plan: its steps from `progress.md` and, under each step, every Worker and Observer run and git checkpoint.

| Event | What it does | What it changes |
|---|---|---|
| `session.start` | Registers the `/karakam-progress` command and a 4-second timer that re-reads the plan's `progress.md` while a plan is on screen. | Nothing; passes the event on unchanged. |
| `command.run` (`karakam-progress` only) | Opens the pane. | Nothing outside the pane. |
| `tool.call` (Skill) | Opens the pane when the `karagoz` skill starts. | Nothing; passes the call on unchanged. |
| `tool.call` (Read, Edit, Write, Bash) | After the call runs, notes which plan's `progress.md` the session is working on and re-reads it. | Nothing; the call and its result pass unchanged. |
| `tool.call` (Bash) | Times Karagöz's `stepgit.sh` checkpoints for the pane. | Nothing; the call and its result pass unchanged. |
| `agent.spawn` | Notes that a Worker or Observer started, for the pane. | Nothing; the spawn and its result pass unchanged. Permission mode and model are left as they are. |
| `turn.complete` | Notes a Worker's or Observer's verdict and token use, for the pane. | Nothing; passes the event on unchanged. |
| `ui.render` | Draws the pane. | Only the pane. |

The pane's state lives in the plugin's own store (`ledger`, `micro`, `isExpanded`). The hooks read your plan files and never write any file.

**Worker stop guard** (`hooks/stopguard.ts`). Registered on `SubagentStop`, and only for karakam's Worker agents.

- **What it does:** when a Worker ends its turn on a progress summary instead of a final report, the guard sends it back once to finish the step. A Worker that stopped half-way would otherwise cost a whole audit-and-refactor round.
- **How it judges:** Haiku reads the Worker's last message, through your session's own model client, at about $0.0001 per stop.
- **What it changes:** that one sub-agent stop. Nothing else, and never the same stop twice. Any error lets the stop through.
- **How to turn it off:** set `KARAKAM_JUDGE=off`.
- **Where it doesn't run:** where an organization manages Claude Code, `SubagentStop` hooks run only for plugins the organization lists in its managed settings. There the Coordinator sends a half-finished Worker back itself, at the cost of a few more turns.
