---
id: mcp
title: MCP tools: connecting Madalean with other assistants
order: 325
section: settings
audience: all
summary: Let another assistant on this computer use Madalean's tools, and give Madalean's models tools of other programs — off until you switch it on.
---

# MCP tools: connecting Madalean with other assistants

**MCP** (*Model Context Protocol*) is a common way for AI assistants to use the tools of other programs. Madalean
speaks it both ways. Everything is set in **Settings › Tools (MCP)**, on the host computer only, and everything is
**off** at first.

## Madalean as an MCP server

Another assistant on this computer (Claude Code, Claude Desktop…) can then:

- **search Mathlib** for the exact names of the installed version;
- **check with Lean** a statement, or a proof of it — with Madalean's strict verdict (no `sorry`, no added axiom);
  the proof cannot change the statement;
- **certify** a computational statement (Sage computes a witness, Lean checks it);
- **explain** a Lean error, or code line by line;
- **search your library** and see **the state of your dossiers**.

These tools **store nothing**: no dossier is created, nothing is added to the library.

To connect it:

1. switch on **“Allow the applications of this computer”**;
2. copy the command shown (Claude Code) or the JSON block (Claude Desktop and other clients);
3. restart the client. Madalean must be running.

Two more switches:

- **“Also through a local address (HTTP)”**: for clients that connect to an `http://127.0.0.1:…` address. It is open
  to this computer only;
- **“Allow Sage computations”**: the client describes a computation in words (“factor x⁴ − 1 over F₅”); Madalean
  runs only **its own verified code**, in the isolated kernel. Code sent by the client is never run.

Paired devices (phone, another computer) **never** have access to it.

## External MCP servers

The other way round, you can give Madalean's models tools of other programs, for instance an MCP server for the Lean
language. Add it by its **command** (Madalean starts it) or its **address**, then:

1. **Test**: Madalean starts it, reads the list of its tools and stops it;
2. **switch it on**;
3. **tick** the tools the models may call during a proof. Nothing is ticked at first.

What Madalean does to protect you:

- the answers of these tools are read as **data**, never as orders; a text that tries to give orders to the model is
  flagged and set aside;
- a tool whose description gives orders to the model is **refused** (it cannot be ticked);
- the program receives **no API key** and no password; every call is limited in time and size;
- only **Lean** decides that a proof is right: an external tool can never make a proof pass.

A server started by a command runs with **your rights**: add only programs you trust.

### Example: an MCP server for Lean

The `lean-lsp-mcp` project (install it yourself, without administrator rights, for instance with `uv`) gives access
to Lean's language server. Command to add: `uvx lean-lsp-mcp`. It reads the files of a Lean project: start it from
the project or set the project in its own configuration (see its documentation).

## The call log

Every call, in either direction, is written down: when, which tool, done or not, how long it took. The log is at the
bottom of the page, and in `logs/mcp-activity.jsonl` of the configuration folder.
