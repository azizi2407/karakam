# Privacy Policy

karakam is a Claude Code plugin: two skills, eight sub-agent definitions and one hooks module. It runs inside your own Claude Code session. This page says what it touches.

## What the plugin collects

Nothing. The plugin has no server, no account, no analytics and no telemetry. It sends nothing to its author or to any third party, and it reads no keys, tokens or credentials.

## What it reads and writes on your machine

- **The skills** write the plan (`methodology.md`, `progress.md`, `steps/`, `logs/`, `reports/`) into the project directory you give them, and the Workers they start change your project's files and make git commits there, as any Claude Code session would.
- **The hooks** read the plan's `progress.md` to draw the progress pane. They never write a file. The pane's state stays in the plugin's own store in your session.

## What goes to a model

Everything the skills and sub-agents do runs through your own Claude Code session, under your own account, settings and permission rules. The plugin adds one model call of its own: when a Worker sub-agent stops, the stop guard sends the last part of that Worker's reply (up to 20,000 characters) to Haiku through your session's own model client, to ask whether the Worker stopped half-way. Nothing else is sent. Set `KARAKAM_JUDGE=off` to turn the guard off.

How your model provider handles that data is set by your agreement with them (for Anthropic, its Privacy Policy and the terms of your plan), not by this plugin.

## Connected services

Sub-agents can use the MCP servers you have connected to your session, under your permission rules. The plugin connects to no service of its own and stores nothing from those services.

## Changes and contact

Changes to this policy are made in this file and are visible in the repository's history. Questions: open an issue at <https://github.com/azizi2407/karakam/issues>.
