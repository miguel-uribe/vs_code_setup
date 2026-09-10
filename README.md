# Portable Python environment manager for VS Code

A project template that makes **every AI coding assistant** in VS Code follow
the same protocol for Python environments: Claude Code, GitHub Copilot, OpenAI
Codex, Gemini, Cursor and Windsurf.

The protocol has three rules:

1. The first time the project is opened, the assistant **asks** which Python
   environment to use.
2. It creates that environment with `uv`.
3. It records the decision in a file and **never asks again**, not even after
   the project is cloned onto a different computer.

It behaves identically on Windows, macOS and Linux, and the folder holding
shared environments can be different on every machine.

> **A note on language.** This guide is in English. The scripts themselves
> still print in Spanish, so the sample output blocks below are shown verbatim
> as you will see them in your terminal.

---

## Table of contents

- [The problem this solves](#the-problem-this-solves)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Tutorial](#tutorial)
  - [Step 1: set up the machine, once](#step-1-set-up-the-machine-once)
  - [Step 2: install the template into a project](#step-2-install-the-template-into-a-project)
  - [Step 3: choose an environment](#step-3-choose-an-environment)
  - [Step 4: daily work](#step-4-daily-work)
  - [Step 5: clone onto another computer](#step-5-clone-onto-another-computer)
  - [Step 6: change your mind mid-project](#step-6-change-your-mind-mid-project)
- [How each AI agent finds out](#how-each-ai-agent-finds-out)
- [Choosing the Python version](#choosing-the-python-version)
- [The three configuration layers](#the-three-configuration-layers)
- [What the script writes into VS Code](#what-the-script-writes-into-vs-code)
- [Command reference](#command-reference)
- [Troubleshooting](#troubleshooting)
- [Repository layout](#repository-layout)
- [Notes and limitations](#notes-and-limitations)

---

## The problem this solves

Ask an AI assistant to install a package and it will guess. It might create a
`.venv` you did not want, call `pip` against your system Python, or invent a
path that only exists on the machine where it was invented. Ask a second
assistant the next day and it guesses differently.

Worse, the guess does not survive a clone. Absolute paths like
`C:\PythonFiles\envs\analytics` mean nothing on a colleague's laptop, so
whatever you configured has to be reconstructed by hand, and the assistant
starts asking all over again.

This template fixes both halves. It gives every assistant one written protocol
to follow, and it separates the **decision** from the **paths** so the decision
can be committed to git while the paths stay local.

---

## How it works

Configuration is split across three layers. This split is the heart of the
design, so it is worth understanding before anything else.

| Layer | Where it lives | What it holds | In git? |
|---|---|---|---|
| Machine | `%APPDATA%\ai-python-bootstrap\config.json` on Windows, `~/.config/ai-python-bootstrap/config.json` elsewhere | Where environments live on **this** computer | No |
| Project | `.ai/env.json` | The decision: local or shared, plus the name | **Yes** |
| Resolved | `.ai/env.local.json` | Absolute paths for **this** computer | No |

The key property is that `.ai/env.json` contains **no absolute paths**. It says
"a shared environment named `analytics`", not
"`C:\PythonFiles\envs\analytics`". Every computer resolves that name against
its own environments folder.

That is why cloning works. The new machine finds a decision it can honor, so
it materializes the environment instead of asking you to make the choice again.

---

## Requirements

Only [`uv`](https://docs.astral.sh/uv/). You do **not** need Python installed
beforehand, because uv downloads an interpreter if none is suitable.

On Windows:

```powershell
winget install --id=astral-sh.uv -e
```

On macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify it:

```bash
uv --version
```

---

## Tutorial

This walks through the whole lifecycle, from a bare machine to a project shared
with a colleague.

> **Where do I run each command?** There is one rule, and it follows the scope
> of what you are changing.
>
> | Scope | Run from | Script path |
> |---|---|---|
> | Machine settings: the environments folder, the default Python version | This repository | `template/.ai/setup_env.py` |
> | Everything else: choosing, syncing or switching a project's environment | The project itself | `.ai/setup_env.py` |
>
> Step 1 is the machine half. Steps 2 through 6 are the project half, and by
> then the project has its own copy of the script, installed in Step 2.
>
> If you see `[Errno 2] No such file or directory`, you are in the wrong half.

### Step 1: set up the machine, once

**Run this from the folder where you cloned this repository.** Machine-level
settings belong here, not in a project.

Tell the tool where shared environments should live on this computer:

```bash
uv run --script template/.ai/setup_env.py --set-envs-root "D:/envs"
```

You can also pin the default Python version for this machine:

```bash
uv run --script template/.ai/setup_env.py --set-default-python 3.13
```

Both flags write to your user configuration and exit immediately. They never
read or touch a project, which is exactly why they belong at the repository
level: the answer applies to the whole computer, so tying it to one project
would be misleading.

You only do this once per machine, and you can skip it entirely. If you never
run it, the script asks the first time it needs a shared environment and saves
your answer. In that case, go straight to Step 2 and come back here whenever
you want to change the folder or the default version.

Both settings land in one file, which you can inspect or delete at any time:

| Platform | Location |
|---|---|
| Windows | `%APPDATA%\ai-python-bootstrap\config.json` |
| macOS and Linux | `~/.config/ai-python-bootstrap/config.json` |

For reference, the environments folder is resolved in this order, most specific
first. What you saved here is item 3:

1. `--envs-root` passed on the command line, for one run only
2. The `AI_ENVS_ROOT` environment variable
3. The saved machine configuration
4. A prompt, whose answer is then saved
5. A built-in default: `C:\PythonFiles\envs` on Windows, `~/.virtualenvs` elsewhere

### Step 2: install the template into a project

From this repository, point the installer at the project you want to configure:

```bash
uv run --script install_ai_config.py --target C:/path/to/your/project
```

Preview it first if you like. Nothing is written in dry-run mode:

```bash
uv run --script install_ai_config.py --target C:/path/to/your/project --dry-run
```

You will see roughly this:

```
Instalando en: C:\path\to\your\project

  copiado: AGENTS.md
  copiado: CLAUDE.md
  copiado: .ai/setup_env.py
  copiado: .ai/setup-env.ps1
  copiado: .ai/setup-env.sh
  copiado: .github/copilot-instructions.md
  creado: .vscode/settings.json
  creado: .vscode/extensions.json
  creado: .vscode/tasks.json
  creado: .claude/settings.json
  creado: .gemini/settings.json
  creado: .gitignore
  creado: .cursor/rules/project.mdc
  creado: .windsurfrules
  creado: GEMINI.md

Configuracion instalada (15 archivos).
```

The installer is careful with projects that already have configuration:

- **Text files** such as `AGENTS.md` and the agent instruction files are copied.
  If one already exists it is skipped, unless you pass `--force`.
- **`.gitignore`** only gains the lines it is missing. It is never overwritten,
  and additions go inside a clearly marked block.
- **JSON files** for VS Code, Claude Code and Gemini are **merged** with what is
  already there. Existing values win, unless you pass `--force`. Lists such as
  extension recommendations gain new entries without losing old ones.

Add `--setup` to launch the environment wizard as soon as the install finishes.

### Step 3: choose an environment

Run the wizard from inside the target project:

```bash
uv run --script .ai/setup_env.py
```

You get four options:

```
Configuracion del ambiente de Python para: your-project

  1) Ambiente LOCAL          -> C:\path\to\your\project\.venv
  2) Ambiente NUEVO en       -> D:\envs
  3) Ambiente EXISTENTE en   -> D:\envs  (3 disponibles)
  4) Sin Python

Selecciona una opcion [1-4]:
```

What each one does:

| Option | Meaning |
|---|---|
| 1, local | Creates `.venv` inside the project folder |
| 2, new shared | Creates one in this machine's central folder, under a name you choose |
| 3, existing shared | Reuses one that already exists in the central folder |
| 4, no Python | Marks the project as not a Python project and silences the question |

Options 1 and 2 also ask **which Python version** you want, because that answer
changes the result. Option 3 does not ask: the version is already fixed by the
environment you are reusing, so offering a choice would be offering a fiction.

You can skip the menu entirely and pass the answer directly, which is what the
AI agents do:

```bash
uv run --script .ai/setup_env.py --mode local --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-new --name analytics --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-existing --name analytics
uv run --script .ai/setup_env.py --mode none
```

When it finishes, reload VS Code with `Ctrl+Shift+P` then
`Developer: Reload Window` so the Python extension picks up the new interpreter.

Check the result at any time:

```bash
uv run --script .ai/setup_env.py --show
```

```
Proyecto            : C:\path\to\your\project
Config de la maquina: C:\Users\you\AppData\Roaming\ai-python-bootstrap\config.json
Carpeta de ambientes: D:\envs
Ambientes ahi       : analytics (py3.12.8)
Python por defecto  : 3.12 (por defecto de la plantilla)
Python instalado    : 3.14.2, 3.13.0, 3.12.8, 3.11.16
```

It then prints both JSON files in full.

### Step 4: daily work

Two things now hold for every Python command in this project.

**Always use `uv`.** Never `python -m venv`, `virtualenv`, `conda`, `pyenv`, or
bare `pip` against the system Python.

**Always pass `--python`**, taking the value from the `pythonPath` field of
`.ai/env.local.json`. This matters when the environment lives outside the
project, because without it uv would create a second `.venv` alongside your
code.

| Task | Command |
|---|---|
| Install a package | `uv pip install --python "<pythonPath>" <package>` |
| Install from requirements | `uv pip install --python "<pythonPath>" -r requirements.txt` |
| List packages | `uv pip list --python "<pythonPath>"` |
| Freeze dependencies | `uv pip freeze --python "<pythonPath>" > requirements.txt` |
| Run a script | `uv run --python "<pythonPath>" script.py` |

If your project uses `pyproject.toml` with `uv sync` and `uv add`, you do not
need the flag. The script writes `UV_PROJECT_ENVIRONMENT` into the VS Code
terminal configuration, so those commands already point at the right
environment in any VS Code terminal.

From the VS Code UI, press `Ctrl+Shift+P`, choose `Tasks: Run Task`, and pick
one of the installed tasks. Their labels appear in Spanish:

| Task label | What it does |
|---|---|
| `Python: configurar ambiente (uv)` | Opens the interactive wizard |
| `Python: sincronizar ambiente en este computador` | Runs `--sync` |
| `Python: ver configuracion actual` | Runs `--show` |
| `Python: cambiar de ambiente` | Runs `--change` |
| `Python: cambiar version de Python del ambiente` | Prompts for a version, runs `--switch-python` |

The installed `tasks.json` also carries two tasks that change machine settings,
`Python: fijar version por defecto de este computador` and
`Python: cambiar carpeta de ambientes de este computador`. Prefer the
repository-level commands from Step 1 for those. A machine setting changed from
inside one project is easy to forget you changed, and it silently affects every
other project on the computer.

On Windows you can also call `.ai\setup-env.ps1`, and on macOS or Linux
`.ai/setup-env.sh`, with exactly the same arguments. Both check that uv is
installed and print an install hint if it is not.

### Step 5: clone onto another computer

This is the payoff. Commit `.ai/env.json` along with the rest of the project.
Do **not** commit `.ai/env.local.json`; the installed `.gitignore` already
excludes it.

On the new machine, the assistant finds `.ai/env.json` with no
`.ai/env.local.json` next to it. That combination means "the decision is made
but not yet materialized here", so it runs:

```bash
uv run --script .ai/setup_env.py --sync
```

The environment is recreated with the same name and the same Python series, but
under **that** computer's environments folder. Nobody is asked anything.

If an environment with that name already exists there, it is reused as is. If
the recorded interpreter has since been deleted, it is rebuilt automatically.

### Step 6: change your mind mid-project

Compatibility problems show up after you have already installed packages. There
are two separate commands, because there are two different intentions.

**Keep the environment, change the interpreter:**

```bash
uv run --script .ai/setup_env.py --switch-python 3.11
```

This preserves the mode, the name and the folder. Before rebuilding, it records
the installed packages in `.ai/packages.backup.txt` and reinstalls them
afterwards. If the project declares `pyproject.toml` or `requirements.txt`,
those take precedence over the backup, because declared dependencies are the
real source of truth and the backup is only a safety net for packages someone
installed by hand.

If a package has no build for the new interpreter, the script warns you and
leaves the list in place so you can review it. It does not try to resolve the
conflict for you.

**Choose a different environment:**

```bash
uv run --script .ai/setup_env.py --change                       # reopen the full menu
uv run --script .ai/setup_env.py --mode shared-existing --name other
```

One warning worth internalizing. Changing the Python version of a **shared**
environment affects every project on this computer that uses it. The script
asks for confirmation in the terminal. `--yes` skips that prompt, and the agent
instructions explicitly forbid assistants from passing it without your
permission, because an agent doing so on its own could break another project's
work silently.

After any of these commands, re-read `pythonPath` from `.ai/env.local.json`.
The interpreter changed, so previously copied commands are stale.

All three commands are documented in the agent instructions, so you can simply
ask your assistant in plain language: "switch this project to Python 3.11".

---

## How each AI agent finds out

| Agent | VS Code extension | File it reads |
|---|---|---|
| Claude Code | `anthropic.claude-code` | `CLAUDE.md`, which imports `AGENTS.md`, plus the `SessionStart` hook in `.claude/settings.json` |
| GitHub Copilot | `GitHub.copilot`, `GitHub.copilot-chat` | `.github/copilot-instructions.md` and `AGENTS.md` |
| OpenAI Codex | `openai.chatgpt` | `AGENTS.md` |
| Gemini | `Google.geminicodeassist` | `GEMINI.md`, which imports `AGENTS.md`, plus `.gemini/settings.json` |
| Cursor | — | `.cursor/rules/project.mdc` |
| Windsurf | — | `.windsurfrules` |

`AGENTS.md` is the single source of truth. Every other file is a bridge that
points back to it, so there is only one document to edit when the rules change.

All five extensions are listed in `.vscode/extensions.json`, so VS Code offers
to install them when the project is first opened.

**Two settings are required for Copilot**, and both are written into
`.vscode/settings.json`:

- `github.copilot.chat.codeGeneration.useInstructionFiles` enables
  `.github/copilot-instructions.md`.
- `chat.useAgentsMdFile` enables `AGENTS.md`. **VS Code ships this turned off**
  because it is still experimental, so without this line Copilot silently
  ignores the file that the whole design treats as authoritative.

Watch out for one case. The installer preserves values the project already has,
so if `chat.useAgentsMdFile` was already set to `false`, it stays `false`. Use
`--force` or fix it by hand.

Gemini reads `GEMINI.md`, which opens with `@AGENTS.md`. The Gemini CLI
resolves that as an import and loads the full document. Because the VS Code
extension does not guarantee resolving imports, the essentials are repeated
below the import line. `.gemini/settings.json` additionally declares
`context.fileName` with both `AGENTS.md` and `GEMINI.md`.

Codex needs no bridge at all. A root `AGENTS.md` is its native format.

The Claude Code hook is the only deterministic part of any of this. It runs
`--agent-context` when a session opens and injects the environment state
straight into the model's context, so correct behavior does not depend on the
model remembering to read a file. Claude Code asks permission the first time it
runs the hook.

The other agents have no hook mechanism. For them the written instruction is
all there is. You can make the file easy to find and hard to misread, which is
what this template does, but you cannot compel the model to follow it.

You can print the same summary yourself:

```bash
uv run --script .ai/setup_env.py --agent-context
```

On a brand-new project it prints:

```
=== Ambiente de Python del proyecto (ai-python-bootstrap) ===
Estado: SIN CONFIGURAR (primera vez).
Instruccion: antes de ejecutar Python o instalar dependencias, PREGUNTA al
usuario cual de estas cuatro opciones quiere y espera su respuesta:
  1. Ambiente local .venv dentro del proyecto
  2. Ambiente nuevo en la carpeta central de este computador (pide el nombre)
  3. Ambiente existente de la carpeta central (muestra la lista con --show)
  4. Sin Python
```

There are five states in total: unconfigured, decided-but-not-resolved,
configured, broken (the recorded interpreter is gone), and no-Python. Each one
prints the exact instruction the agent should follow.

---

## Choosing the Python version

The suggested version comes from the first of these sources that exists:

1. `--python-version` on the command line
2. A `.python-version` file at the project root
3. `defaultPythonVersion` in this machine's configuration
4. `3.12`, the template's built-in fallback

`.python-version` deliberately outranks the machine configuration. It is a
project file, and it is the same standard uv and pyenv already read, so a
project that has one works with no extra setup.

The menu tells you which source a suggestion came from, so you are never left
wondering why a particular number appeared.

You may write a series such as `3.12` or an exact version such as `3.12.8`. If
it is not installed, uv downloads it.

`.ai/env.json` always stores the **requested series**, never the resolved
patch. That way another machine is not forced to download a byte-identical
interpreter. The resolved patch is recorded in `.ai/env.local.json` instead.

---

## The three configuration layers

### `.ai/env.json`, portable, committed to git

```json
{
  "schemaVersion": 3,
  "usesPython": true,
  "mode": "shared",
  "envName": "analytics",
  "pythonVersion": "3.12",
  "manager": "uv"
}
```

`mode` is `local`, `shared` or `none`. `envName` applies only when the mode is
`shared`.

### `.ai/env.local.json`, machine-specific, git-ignored

```json
{
  "schemaVersion": 3,
  "envPath": "/path/to/envs/analytics",
  "pythonPath": "/path/to/envs/analytics/bin/python",
  "envsRoot": "/path/to/envs",
  "pythonVersion": "3.12",
  "pythonVersionResolved": "3.12.8",
  "platform": "linux",
  "resolvedAt": "2026-09-10T11:26:03-05:00"
}
```

If `pythonPath` points somewhere that no longer exists, run `--sync` to rebuild.

**Never edit either file by hand.** Use the commands instead, so the two files
stay consistent with each other and with VS Code.

---

## What the script writes into VS Code

Every time the environment changes, `.vscode/settings.json` is updated with:

- `python.defaultInterpreterPath`, so the Python extension selects the right
  interpreter.
- `terminal.integrated.env.windows`, `.osx` or `.linux`, carrying
  `UV_PROJECT_ENVIRONMENT` so `uv sync` and `uv add` target the correct
  environment from any VS Code terminal.
- `python.venvPath` when the environment is shared, so the interpreter picker
  lists the central folder.

Choosing `--mode none` clears all of these, so a project marked as
non-Python does not keep pointing at a stale environment.

The file is parsed as JSONC, meaning comments and trailing commas are tolerated
rather than causing your settings to be discarded.

---

## Command reference

### Installer

| Command | Effect |
|---|---|
| `--target <path>` | Required. The project to configure. |
| `--dry-run` | Show what would change, write nothing. |
| `--force` | Overwrite existing files. Use with care. |
| `--setup` | Launch the environment wizard when the install finishes. |

### Environment script, project flags

Run from the project, as `uv run --script .ai/setup_env.py <flags>`.

| Command | Effect |
|---|---|
| *(no flags)* | Interactive menu |
| `--mode local` | Create `.venv` in the project |
| `--mode shared-new --name <n>` | Create a new shared environment |
| `--mode shared-existing --name <n>` | Reuse an existing shared environment |
| `--mode none` | Mark the project as not using Python |
| `--python-version <v>` | Series or exact version, for the two creating modes |
| `--sync` | Materialize `.ai/env.json` on this machine |
| `--show` | Print the full current state |
| `--agent-context` | Print a short state summary for an AI agent |
| `--change` | Reopen the menu to pick a different environment |
| `--switch-python <v>` | Rebuild the current environment on another interpreter |
| `--force` | Rebuild even if the environment already exists |
| `--yes` | Skip the shared-environment confirmation prompt |
| `--envs-root <path>` | Override the environments folder for this run only |

### Environment script, machine flags

Run from this repository, as
`uv run --script template/.ai/setup_env.py <flags>`. Both write your user
configuration and exit without reading any project.

| Command | Effect |
|---|---|
| `--set-envs-root <path>` | Save this machine's environments folder, then exit |
| `--set-default-python <v>` | Save this machine's default Python version, then exit |

---

## Troubleshooting

**`can't open file '...\.ai\setup_env.py': [Errno 2] No such file or
directory`.** You are running from a folder that has no `.ai/` in it, most
often this repository itself. In this repository the script lives at
`template/.ai/setup_env.py`. A project only gets its own `.ai/setup_env.py`
after you install the template into it, as described in Step 2.

The two machine-level flags, `--set-envs-root` and `--set-default-python`, are
meant to be run from this repository in the first place:

```bash
uv run --script template/.ai/setup_env.py --set-envs-root "C:/PythonFiles/envs"
```

**The menu fails with "No hay terminal interactiva".** You are running without a
TTY, which happens in CI and inside some agent terminals. Pass `--mode`
explicitly instead of relying on the menu.

**Copilot ignores `AGENTS.md`.** Check that `chat.useAgentsMdFile` is `true` in
`.vscode/settings.json`. If the project already had it set to `false`, the
installer left it alone by design.

**The interpreter disappeared.** Run `--sync`. The environment is rebuilt from
the committed decision.

**`uv sync` created an unexpected `.venv`.** The environment lives outside the
project, and the command ran somewhere `UV_PROJECT_ENVIRONMENT` is not set.
Either use a VS Code terminal, or pass `--python "<pythonPath>"` explicitly.

**A package will not install after switching Python versions.** It has no build
for the new interpreter. The list is preserved in `.ai/packages.backup.txt` for
you to review. The script does not resolve this automatically.

**Which Python actually runs the script?** uv is a Rust binary, so it needs no
Python to start. It finds an interpreter satisfying the script's
`requires-python = ">=3.9"` header, downloading one if necessary, and creates a
throwaway environment in its cache purely to run the script. That environment is
empty, is not your project's environment, and never touches it. The two
interpreters have no reason to match.

The script has no dependencies, so any Python 3.9 or newer works too:

```bash
python .ai/setup_env.py --show
```

---

## Repository layout

```
install_ai_config.py     The installer
template/                Everything copied into the target project
  AGENTS.md              Single source of truth for all agents
  CLAUDE.md              Bridge for Claude Code
  _gitignore             Installed as .gitignore, merged
  .ai/setup_env.py       All of the logic
  .ai/setup-env.ps1      Windows launcher
  .ai/setup-env.sh       macOS and Linux launcher
  .claude/settings.json  SessionStart hook
  .github/               Copilot instructions
  .gemini/settings.json  Tells Gemini to read AGENTS.md
  .vscode/               settings, tasks and recommended extensions
docs/DECISIONES.md       Why it is built this way
```

The template lives in its own folder so that this repository can have its own
configuration, separate from the configuration it distributes. The template's
`.gitignore` is named `_gitignore` here so git does not apply it to the template
files themselves; the installer writes it under its real name in the target.

---

## Notes and limitations

- Changing environments does not delete the old one. If you move from shared to
  local, the shared environment stays where it was, in case other projects use
  it.
- `uv venv` refuses to overwrite an existing environment, so the script passes
  `--clear` when the folder is already occupied.
- Merging `settings.json` **loses the comments** in the original file. The
  output is clean JSON. All values are preserved.
- The Claude Code hook needs your approval the first time it runs.
- `--set-envs-root` and `--set-default-python` write outside the project, into
  the machine configuration, and affect every project on the computer. That is
  intentional, and it is why this guide runs them from the repository rather
  than from a project. Worth knowing before running either on a shared machine.
- There are no automated tests. Verification has been manual, covering clean
  installs, installs over existing configuration, all four modes, cloning to a
  different environments folder, recovery after deleting an interpreter, every
  branch of the version menu, switching versions with packages installed,
  switching to a version that is not installed, and the shared-environment
  confirmation both with and without `--yes`.
- The scripts and the agent instruction files are written in Spanish. Only this
  guide is in English.
