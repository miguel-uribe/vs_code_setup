#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Instala la plantilla de configuracion de ambientes de Python en un proyecto.

    uv run --script install_ai_config.py --target /ruta/al/proyecto
    uv run --script install_ai_config.py --target . --setup
    uv run --script install_ai_config.py --target . --dry-run

Que hace con cada archivo:

  - Archivos de texto (AGENTS.md, .ai/, instrucciones de agentes): se copian.
    Si ya existen, se omiten salvo que pases --force.
  - .gitignore: se agregan solo las lineas que falten. Nunca se sobrescribe.
  - .vscode/settings.json, .vscode/extensions.json, .vscode/tasks.json,
    .claude/settings.json y .gemini/settings.json: se FUSIONAN con lo que ya
    tenga el proyecto. Lo existente gana, salvo con --force.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "template"

# Archivos que se copian tal cual.
COPY_ITEMS = [
    "AGENTS.md",
    "CLAUDE.md",
    ".ai/setup_env.py",
    ".ai/setup-env.ps1",
    ".ai/setup-env.sh",
    ".github/copilot-instructions.md",
]

# Archivos JSON que se fusionan en lugar de sobrescribirse.
MERGE_ITEMS = [
    ".vscode/settings.json",
    ".vscode/extensions.json",
    ".vscode/tasks.json",
    ".claude/settings.json",
    ".gemini/settings.json",
]

BRIDGE = """# Instrucciones del proyecto

Las reglas completas estan en `AGENTS.md`, en la raiz del repositorio. Leelo
antes de trabajar.

Regla critica: antes de ejecutar Python o instalar dependencias, revisa `.ai/`.
Si existe `env.local.json`, usa su campo `pythonPath`. Si solo existe `env.json`,
ejecuta `uv run --script .ai/setup_env.py --sync`. Si no existe ninguno, pregunta
al usuario las cuatro opciones de ambiente descritas en `AGENTS.md` y, para las
opciones 1 y 2, tambien la version de Python.

Atajo para ver el estado: `uv run --script .ai/setup_env.py --agent-context`.

Si a mitad del trabajo aparece un problema de compatibilidad, no edites los
archivos de `.ai/` a mano ni crees ambientes por tu cuenta:

    uv run --script .ai/setup_env.py --switch-python 3.11   # otra version
    uv run --script .ai/setup_env.py --change               # otro ambiente

Cambiar la version de un ambiente compartido afecta a los demas proyectos de
este computador. No pases `--yes` sin permiso explicito del usuario.

Los ambientes se gestionan solo con `uv`, pasando siempre
`--python "<pythonPath>"` en los comandos `uv pip`. Nunca escribas rutas
absolutas de ambientes en el codigo: cambian de un computador a otro.
"""

# Gemini CLI resuelve importaciones con @ruta dentro del archivo de contexto.
# Se importa AGENTS.md y ademas se repite lo esencial, porque Gemini Code Assist
# en VS Code lee el archivo pero no garantiza resolver la importacion.
GEMINI_BRIDGE = """@AGENTS.md

""" + BRIDGE

CURSOR_HEADER = """---
description: Reglas del proyecto
alwaysApply: true
---

"""

BRIDGES = {
    Path(".cursor/rules/project.mdc"): CURSOR_HEADER + BRIDGE,
    Path(".windsurfrules"): BRIDGE,
    Path("GEMINI.md"): GEMINI_BRIDGE,
}


# ------------------------------------------------------------------ json utils

def strip_jsonc(text: str) -> str:
    """Quita comentarios // y /* */ y comas colgantes. VS Code acepta JSONC."""
    out: list[str] = []
    i, n, in_string = 0, len(text), False
    while i < n:
        char = text[i]
        if in_string:
            out.append(char)
            if char == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(char)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_jsonc(path: Path):
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(strip_jsonc(raw))


# --------------------------------------------------------------------- fusiones

def merge_settings(existing: dict, incoming: dict, force: bool) -> dict:
    result = dict(existing)
    for key, value in incoming.items():
        if key not in result or force:
            result[key] = value
    return result


def merge_extensions(existing: dict, incoming: dict, force: bool) -> dict:
    result = dict(existing)
    current = result.get("recommendations")
    current = list(current) if isinstance(current, list) else []
    for ext in incoming.get("recommendations", []):
        if ext not in current:
            current.append(ext)
    result["recommendations"] = current
    return result


def merge_tasks(existing: dict, incoming: dict, force: bool) -> dict:
    result = dict(existing)
    result.setdefault("version", incoming.get("version", "2.0.0"))

    current_tasks = result.get("tasks")
    current_tasks = list(current_tasks) if isinstance(current_tasks, list) else []
    labels = {t.get("label") for t in current_tasks if isinstance(t, dict)}
    for task in incoming.get("tasks", []):
        if task.get("label") not in labels:
            current_tasks.append(task)
    result["tasks"] = current_tasks

    current_inputs = result.get("inputs")
    current_inputs = list(current_inputs) if isinstance(current_inputs, list) else []
    ids = {i.get("id") for i in current_inputs if isinstance(i, dict)}
    for item in incoming.get("inputs", []):
        if item.get("id") not in ids:
            current_inputs.append(item)
    if current_inputs:
        result["inputs"] = current_inputs
    return result


def merge_claude_settings(existing: dict, incoming: dict, force: bool) -> dict:
    result = dict(existing)

    hooks = dict(result.get("hooks") or {})
    for event, entries in (incoming.get("hooks") or {}).items():
        current = list(hooks.get(event) or [])
        existing_commands = {
            inner.get("command")
            for entry in current if isinstance(entry, dict)
            for inner in (entry.get("hooks") or []) if isinstance(inner, dict)
        }
        for entry in entries:
            commands = {
                inner.get("command")
                for inner in (entry.get("hooks") or []) if isinstance(inner, dict)
            }
            if not commands & existing_commands:
                current.append(entry)
        hooks[event] = current
    if hooks:
        result["hooks"] = hooks

    permissions = dict(result.get("permissions") or {})
    allow = list(permissions.get("allow") or [])
    for rule in (incoming.get("permissions") or {}).get("allow", []):
        if rule not in allow:
            allow.append(rule)
    if allow:
        permissions["allow"] = allow
        result["permissions"] = permissions

    return result


def merge_gemini_settings(existing: dict, incoming: dict, force: bool) -> dict:
    """Fusiona context.fileName sin perder los nombres que el proyecto ya tenga."""
    result = dict(existing)
    context = dict(result.get("context") or {})

    current = context.get("fileName")
    if isinstance(current, str):
        current = [current]
    current = list(current) if isinstance(current, list) else []
    for name in (incoming.get("context") or {}).get("fileName", []):
        if name not in current:
            current.append(name)
    context["fileName"] = current
    result["context"] = context

    for key, value in incoming.items():
        if key != "context" and (key not in result or force):
            result[key] = value
    return result


MERGERS = {
    ".vscode/settings.json": merge_settings,
    ".vscode/extensions.json": merge_extensions,
    ".vscode/tasks.json": merge_tasks,
    ".claude/settings.json": merge_claude_settings,
    ".gemini/settings.json": merge_gemini_settings,
}


# --------------------------------------------------------------------- acciones

class Installer:
    def __init__(self, target: Path, force: bool, dry_run: bool) -> None:
        self.target = target
        self.force = force
        self.dry_run = dry_run
        self.changes = 0

    def report(self, verb: str, item: str) -> None:
        prefix = "  [dry-run] " if self.dry_run else "  "
        print(f"{prefix}{verb}: {item}")
        if verb != "omitido":
            self.changes += 1

    def write_text(self, rel: str, content: str, verb: str) -> None:
        dst = self.target / rel
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        self.report(verb, rel)

    def copy_plain(self) -> None:
        for rel in COPY_ITEMS:
            src, dst = SOURCE / rel, self.target / rel
            if not src.exists():
                print(f"  ADVERTENCIA: falta en la plantilla: {rel}")
                continue
            if dst.exists() and not self.force:
                self.report("omitido", f"{rel} (ya existe)")
                continue
            if not self.dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            self.report("copiado", rel)

    def merge_json(self) -> None:
        for rel in MERGE_ITEMS:
            src, dst = SOURCE / rel, self.target / rel
            if not src.exists():
                continue
            incoming = load_jsonc(src)
            if not dst.exists():
                self.write_text(rel, json.dumps(incoming, indent=2) + "\n", "creado")
                continue
            try:
                existing = load_jsonc(dst)
            except json.JSONDecodeError:
                self.report("omitido", f"{rel} (no se pudo interpretar el existente)")
                continue
            merged = MERGERS[rel](existing, incoming, self.force)
            if merged == existing:
                self.report("omitido", f"{rel} (ya estaba al dia)")
                continue
            self.write_text(rel, json.dumps(merged, indent=2) + "\n", "fusionado")

    def merge_gitignore(self) -> None:
        src = SOURCE / "_gitignore"
        if not src.exists():
            return
        dst = self.target / ".gitignore"
        incoming = src.read_text(encoding="utf-8").splitlines()
        if not dst.exists():
            self.write_text(".gitignore", "\n".join(incoming) + "\n", "creado")
            return
        current = dst.read_text(encoding="utf-8").splitlines()
        present = {line.strip() for line in current}
        missing = [
            line for line in incoming
            if line.strip() and not line.strip().startswith("#")
            and line.strip() not in present
        ]
        if not missing:
            self.report("omitido", ".gitignore (ya estaba al dia)")
            return
        block = ["", "# --- ai-python-bootstrap ---", *missing,
                 "# --- fin ai-python-bootstrap ---"]
        body = "\n".join(current + block) + "\n"
        self.write_text(".gitignore", body, "actualizado")

    def write_bridges(self) -> None:
        for rel, content in BRIDGES.items():
            dst = self.target / rel
            if dst.exists() and not self.force:
                self.report("omitido", f"{rel.as_posix()} (ya existe)")
                continue
            self.write_text(rel.as_posix(), content, "creado")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Instala la configuracion de ambientes de Python en un proyecto.")
    parser.add_argument("--target", required=True, help="Carpeta del proyecto destino.")
    parser.add_argument("--force", action="store_true",
                        help="Sobrescribe archivos existentes. Cuidado en proyectos "
                             "con configuracion propia.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Muestra lo que haria sin escribir nada.")
    parser.add_argument("--setup", action="store_true",
                        help="Lanza el asistente de ambiente al terminar.")
    args = parser.parse_args()

    if not SOURCE.is_dir():
        sys.exit(f"ERROR: no se encontro la plantilla en {SOURCE}")

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        sys.exit(f"ERROR: la carpeta destino no existe: {target}")
    if target == SOURCE or SOURCE in target.parents:
        sys.exit("ERROR: el destino no puede estar dentro de la propia plantilla.")

    print(f"\nInstalando en: {target}\n")
    installer = Installer(target, args.force, args.dry_run)
    installer.copy_plain()
    installer.merge_json()
    installer.merge_gitignore()
    installer.write_bridges()

    if args.dry_run:
        print(f"\nDry-run: {installer.changes} archivos cambiarian. No se escribio nada.\n")
        return

    print(f"\nConfiguracion instalada ({installer.changes} archivos).")

    setup = target / ".ai" / "setup_env.py"
    if args.setup:
        print()
        subprocess.run(["uv", "run", "--script", str(setup)], cwd=str(target))
    else:
        print("Ejecuta el asistente de ambiente con:")
        print(f'  uv run --script "{setup}"')
        print()


if __name__ == "__main__":
    main()
