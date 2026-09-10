#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Configura el ambiente de Python del proyecto usando uv.

Separa la configuracion en tres capas:

  1. Maquina  -> %APPDATA%/ai-python-bootstrap/config.json  (o ~/.config/...)
                 Donde vive la carpeta de ambientes en ESTE computador.
  2. Proyecto -> .ai/env.json         Portable. Se versiona en git.
  3. Local    -> .ai/env.local.json   Rutas absolutas. Se ignora en git.

Uso:
    uv run --script .ai/setup_env.py                       # menu interactivo
    uv run --script .ai/setup_env.py --mode local --python-version 3.12
    uv run --script .ai/setup_env.py --mode shared-new --name mi-proyecto
    uv run --script .ai/setup_env.py --mode shared-existing --name mi-proyecto
    uv run --script .ai/setup_env.py --mode none
    uv run --script .ai/setup_env.py --sync                # materializa en otra maquina
    uv run --script .ai/setup_env.py --show
    uv run --script .ai/setup_env.py --agent-context       # resumen para agentes de IA

Cambiar de opinion a mitad del trabajo:
    uv run --script .ai/setup_env.py --change              # vuelve a abrir el menu
    uv run --script .ai/setup_env.py --switch-python 3.11  # misma carpeta, otra version
    uv run --script .ai/setup_env.py --mode shared-existing --name otro

Ajustes de este computador:
    uv run --script .ai/setup_env.py --set-envs-root "D:/envs"
    uv run --script .ai/setup_env.py --set-default-python 3.13
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 3
MIN_SUPPORTED_SCHEMA = 2
APP_NAME = "ai-python-bootstrap"
IS_WINDOWS = os.name == "nt"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_DIR = PROJECT_ROOT / ".ai"
ENV_FILE = AI_DIR / "env.json"
LOCAL_FILE = AI_DIR / "env.local.json"
VSCODE_DIR = PROJECT_ROOT / ".vscode"
SETTINGS_FILE = VSCODE_DIR / "settings.json"

# Version usada cuando nadie dice otra cosa. Ultimo eslabon de la cadena de
# resolucion de requested_python_version().
DEFAULT_PYTHON_VERSION = "3.12"

PACKAGES_BACKUP = "packages.backup.txt"
INVALID_NAME_CHARS = '\\/:*?"<>|'
TERMINAL_ENV_KEYS = (
    "terminal.integrated.env.windows",
    "terminal.integrated.env.osx",
    "terminal.integrated.env.linux",
)


# --------------------------------------------------------------- presentacion

def step(msg: str) -> None:
    print(f"==> {msg}")


def ok(msg: str) -> None:
    print(f"    {msg}")


def warn(msg: str) -> None:
    print(f"    Aviso: {msg}", file=sys.stderr)


def fail(msg: str) -> None:
    print(f"\nERROR: {msg}\n", file=sys.stderr)
    sys.exit(1)


def ask(prompt: str) -> str:
    """
    input() con final digno.

    isatty() no es de fiar: hay terminales de agentes y de CI donde dice que si
    y la primera lectura da EOF. Sin esto, el script muere con un traceback.
    """
    try:
        return input(prompt)
    except EOFError:
        fail("No hay entrada interactiva disponible.\n"
             "Pasa las respuestas por linea de comandos (--mode, --name,\n"
             "--python-version, --envs-root) o confirma con --yes.")
    except KeyboardInterrupt:
        print()
        fail("Cancelado por el usuario. No se modifico nada.")
    raise SystemExit(1)


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


def read_json(path: Path, tolerate_comments: bool = False) -> dict | None:
    """Devuelve None si no se puede interpretar; {} si el archivo esta vacio."""
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        if not tolerate_comments:
            return None
    try:
        return json.loads(strip_jsonc(raw))
    except json.JSONDecodeError:
        return None


def write_json(path: Path, payload: dict) -> None:
    """Escritura atomica: primero un temporal, luego reemplazo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# ------------------------------------------------------ configuracion maquina

def machine_config_path() -> Path:
    """Ruta del archivo de configuracion propio de este computador."""
    override = os.environ.get("AI_BOOTSTRAP_CONFIG")
    if override:
        return Path(override).expanduser()

    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / APP_NAME / "config.json"


def default_envs_root() -> Path:
    if IS_WINDOWS:
        return Path("C:/PythonFiles/envs")
    return Path.home() / ".virtualenvs"


def read_machine_config() -> dict:
    path = machine_config_path()
    data = read_json(path)
    if data is None and path.exists():
        warn(f"no se pudo leer {path}; se ignora.")
        return {}
    return data or {}


def write_machine_config(data: dict) -> Path:
    path = machine_config_path()
    write_json(path, {"schemaVersion": SCHEMA_VERSION, **data})
    return path


def resolve_envs_root(cli_value: str | None, allow_prompt: bool = True) -> Path:
    """
    Orden de resolucion:
      1. --envs-root en la linea de comandos
      2. variable de entorno AI_ENVS_ROOT
      3. config de la maquina
      4. preguntar al usuario y guardar
      5. valor por defecto segun el sistema operativo
    """
    if cli_value:
        return Path(cli_value).expanduser()

    from_env = os.environ.get("AI_ENVS_ROOT")
    if from_env:
        return Path(from_env).expanduser()

    cfg = read_machine_config()
    if cfg.get("envsRoot"):
        return Path(cfg["envsRoot"]).expanduser()

    suggested = default_envs_root()
    if not allow_prompt or not sys.stdin.isatty():
        return suggested

    print()
    print("Este computador todavia no tiene una carpeta de ambientes definida.")
    answer = ask(f"Ruta para los ambientes compartidos [{suggested}]: ").strip()
    root = Path(answer).expanduser() if answer else suggested
    path = write_machine_config({**read_machine_config(), "envsRoot": str(root)})
    ok(f"Guardado en {path}")
    return root


# ------------------------------------------------------------------ utilidades

def require_uv() -> str:
    uv = shutil.which("uv")
    if uv:
        return uv
    hint = (
        "winget install --id=astral-sh.uv -e"
        if IS_WINDOWS
        else "curl -LsSf https://astral.sh/uv/install.sh | sh"
    )
    fail(f"uv no esta instalado o no esta en el PATH.\nInstalalo con:\n    {hint}")
    raise SystemExit(1)  # inalcanzable


def venv_python(env_path: Path) -> Path:
    """Ruta del interprete dentro de un ambiente, segun el sistema operativo."""
    if IS_WINDOWS:
        return env_path / "Scripts" / "python.exe"
    return env_path / "bin" / "python"


def is_valid_venv(env_path: Path) -> bool:
    return venv_python(env_path).exists() and (env_path / "pyvenv.cfg").exists()


def version_from_cfg(env_path: Path) -> str | None:
    """Lee la version de Python de pyvenv.cfg sin lanzar el interprete."""
    cfg = env_path / "pyvenv.cfg"
    if not cfg.exists():
        return None
    try:
        for line in cfg.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() in ("version", "version_info"):
                return value.strip() or None
    except OSError:
        pass
    return None


def interpreter_version(python_exe: Path) -> str | None:
    """Version exacta del interprete, con el parche incluido."""
    # pyvenv.cfg es gratis, pero cuando se pidio una serie ('3.11') uv anota
    # justamente eso. Solo sirve si trae los tres numeros.
    cached = version_from_cfg(python_exe.parent.parent)
    if cached and len(cached.split(".")) >= 3:
        return cached
    try:
        out = subprocess.run(
            [str(python_exe), "-c", "import platform; print(platform.python_version())"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return cached


def requested_python_version(cli_value: str | None) -> str:
    """
    Version PEDIDA, no la resuelta. Es lo que se versiona en git.

    Orden:
      1. --python-version (o lo que respondio el usuario en el menu)
      2. archivo .python-version en la raiz del proyecto
      3. defaultPythonVersion en la config de este computador
      4. DEFAULT_PYTHON_VERSION
    """
    if cli_value:
        return cli_value.strip()
    version_file = PROJECT_ROOT / ".python-version"
    if version_file.exists():
        text = version_file.read_text(encoding="utf-8").strip()
        if text:
            return text
    cfg = read_machine_config()
    return cfg.get("defaultPythonVersion") or DEFAULT_PYTHON_VERSION


def python_version_source(cli_value: str | None) -> str:
    """De donde salio la version. Solo para explicarselo al usuario."""
    if cli_value:
        return "indicada en el comando"
    version_file = PROJECT_ROOT / ".python-version"
    if version_file.exists() and version_file.read_text(encoding="utf-8").strip():
        return "del archivo .python-version"
    if read_machine_config().get("defaultPythonVersion"):
        return "por defecto de este computador"
    return "por defecto de la plantilla"


def validate_python_version(value: str) -> None:
    """Sanidad basica. uv acepta '3.12', '3.12.8' y cosas como 'pypy@3.11'."""
    clean = value.strip()
    if not clean:
        fail("La version de Python no puede estar vacia.")
    if any(ch in clean for ch in '\\/:*?"<>|'):
        fail(f"'{value}' no parece una version de Python. Usa 3.12 o 3.12.8.")


def installed_python_versions() -> list[str]:
    """Versiones ya disponibles en este computador, segun uv. Best effort."""
    try:
        out = subprocess.run(
            ["uv", "python", "list", "--only-installed", "--output-format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return []
        data = json.loads(out.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        return []
    versions: list[str] = []
    for item in data if isinstance(data, list) else []:
        version = item.get("version") if isinstance(item, dict) else None
        if isinstance(version, str) and version not in versions:
            versions.append(version)
    return versions


def prompt_python_version(default: str, source: str) -> str:
    """Pregunta la version. La sugerencia es la que resolvio la cadena normal."""
    print()
    installed = installed_python_versions()
    if installed:
        print(f"  Ya instaladas aqui: {', '.join(installed)}")
    print("  Escribe una serie (3.12) o una version exacta (3.12.8).")
    print("  Si no la tienes, uv la descarga sola.")
    answer = ask(f"Version de Python [{default}] ({source}): ").strip()
    chosen = answer or default
    validate_python_version(chosen)
    return chosen


def list_existing_envs(envs_root: Path) -> list[tuple[str, str]]:
    """Devuelve (nombre, version) de cada ambiente valido en la carpeta."""
    if not envs_root.is_dir():
        return []
    found: list[tuple[str, str]] = []
    try:
        entries = sorted(envs_root.iterdir())
    except OSError:
        return []
    for entry in entries:
        if entry.is_dir() and is_valid_venv(entry):
            found.append((entry.name, version_from_cfg(entry) or "?"))
    return found


def python_series(version: str) -> str:
    """'3.12.8' -> '3.12'. Lo que se versiona en git debe ser la serie."""
    parts = version.split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return version


def format_env_list(envs: list[tuple[str, str]]) -> str:
    return ", ".join(f"{name} (py{ver})" for name, ver in envs) or "(ninguno)"


def validate_env_name(name: str) -> None:
    clean = name.strip()
    if not clean:
        fail("El nombre del ambiente no puede estar vacio.")
    if clean in (".", ".."):
        fail(f"'{name}' no es un nombre de carpeta valido.")
    if any(ch in clean for ch in INVALID_NAME_CHARS):
        fail(f"El nombre '{name}' tiene caracteres no validos para una carpeta.")


# ----------------------------------------------------------- escritura archivos

def write_env_file(*, uses_python: bool, mode: str, env_name: str | None,
                   python_version: str | None) -> None:
    """Archivo PORTABLE. Sin rutas absolutas. Se versiona en git."""
    write_json(ENV_FILE, {
        "schemaVersion": SCHEMA_VERSION,
        "usesPython": uses_python,
        "mode": mode,                     # local | shared | none
        "envName": env_name,              # solo relevante si mode == shared
        "pythonVersion": python_version,  # serie pedida, p.ej. "3.12"
        "manager": "uv",
    })


def write_local_file(*, env_path: Path | None, python_path: Path | None,
                     envs_root: Path | None, python_version: str | None,
                     resolved_version: str | None) -> None:
    """Archivo LOCAL. Rutas absolutas de ESTA maquina. Va en .gitignore."""
    write_json(LOCAL_FILE, {
        "schemaVersion": SCHEMA_VERSION,
        "envPath": str(env_path) if env_path else None,
        "pythonPath": str(python_path) if python_path else None,
        "envsRoot": str(envs_root) if envs_root else None,
        "pythonVersion": python_version,
        "pythonVersionResolved": resolved_version,
        "platform": sys.platform,
        "resolvedAt": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    })


def terminal_env_key() -> str:
    if IS_WINDOWS:
        return "terminal.integrated.env.windows"
    if sys.platform == "darwin":
        return "terminal.integrated.env.osx"
    return "terminal.integrated.env.linux"


def update_vscode_settings(python_path: Path | None, env_path: Path | None,
                           envs_root: Path | None) -> None:
    VSCODE_DIR.mkdir(parents=True, exist_ok=True)

    settings: dict = {}
    if SETTINGS_FILE.exists():
        parsed = read_json(SETTINGS_FILE, tolerate_comments=True)
        if parsed is None:
            backup = SETTINGS_FILE.with_suffix(".json.bak")
            shutil.copy2(SETTINGS_FILE, backup)
            warn(f"settings.json no se pudo interpretar. Respaldo en {backup}")
        else:
            settings = parsed

    if python_path is None:
        # Proyecto sin Python: se limpia todo rastro del ambiente anterior.
        settings.pop("python.defaultInterpreterPath", None)
        settings.pop("python.venvPath", None)
        for key in TERMINAL_ENV_KEYS:
            term_env = settings.get(key)
            if isinstance(term_env, dict):
                term_env.pop("UV_PROJECT_ENVIRONMENT", None)
                if term_env:
                    settings[key] = term_env
                else:
                    settings.pop(key, None)
    else:
        settings["python.defaultInterpreterPath"] = str(python_path)
        settings["python.terminal.activateEnvironment"] = True
        if envs_root is not None:
            settings["python.venvPath"] = str(envs_root)
        else:
            settings.pop("python.venvPath", None)
        key = terminal_env_key()
        term_env = settings.get(key)
        term_env = dict(term_env) if isinstance(term_env, dict) else {}
        term_env["UV_PROJECT_ENVIRONMENT"] = str(env_path)
        settings[key] = term_env

    write_json(SETTINGS_FILE, settings)


# ----------------------------------------------------------- creacion ambiente

def create_venv(env_path: Path, python_version: str) -> None:
    step(f"Creando ambiente con uv (Python {python_version})")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "venv", str(env_path), "--python", python_version]
    if env_path.exists():
        # uv se niega a pisar un ambiente existente si no se lo pides.
        cmd.append("--clear")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail(f"'uv venv' fallo con codigo {result.returncode}.")


def ensure_venv(env_path: Path, python_version: str, force: bool) -> None:
    """Crea el ambiente salvo que ya exista uno valido y no se pida rehacerlo."""
    if is_valid_venv(env_path) and not force:
        step("Reutilizando el ambiente que ya existe")
        ok(f"{env_path}  (Python {version_from_cfg(env_path) or '?'})")
        return
    create_venv(env_path, python_version)


def snapshot_packages(env_path: Path) -> Path | None:
    """
    Anota los paquetes del ambiente antes de rehacerlo.

    Sirve para que cambiar de version de Python no borre en silencio lo que el
    usuario ya tenia instalado.
    """
    python_path = venv_python(env_path)
    if not python_path.exists():
        return None
    try:
        out = subprocess.run(
            ["uv", "pip", "freeze", "--python", str(python_path)],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None

    AI_DIR.mkdir(parents=True, exist_ok=True)
    backup = AI_DIR / PACKAGES_BACKUP
    backup.write_text(out.stdout, encoding="utf-8")
    count = len([line for line in out.stdout.splitlines() if line.strip()])
    step("Anotando los paquetes del ambiente actual")
    ok(f"{count} paquetes guardados en {backup}")
    return backup


def install_dependencies(python_path: Path, env_path: Path,
                         snapshot: Path | None = None) -> None:
    """Instala dependencias declaradas; si no hay, restaura el snapshot."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    requirements = PROJECT_ROOT / "requirements.txt"

    if pyproject.exists():
        step("Sincronizando dependencias de pyproject.toml")
        env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(env_path)}
        result = subprocess.run(["uv", "sync"], cwd=str(PROJECT_ROOT), env=env)
        if result.returncode != 0:
            warn("'uv sync' fallo. Revisa pyproject.toml y vuelve a intentarlo.")
        return

    if requirements.exists():
        step("Instalando requirements.txt")
        result = subprocess.run(
            ["uv", "pip", "install", "--python", str(python_path),
             "-r", str(requirements)]
        )
        if result.returncode != 0:
            warn("'uv pip install' fallo. Revisa requirements.txt.")
        return

    if snapshot is not None and snapshot.exists():
        step("Reinstalando los paquetes que tenia el ambiente anterior")
        result = subprocess.run(
            ["uv", "pip", "install", "--python", str(python_path),
             "-r", str(snapshot)]
        )
        if result.returncode != 0:
            warn(f"Algunos paquetes no se pudieron reinstalar. La lista sigue en "
                 f"{snapshot}; revisala y ajusta las versiones a mano.")


def finalize(mode: str, env_name: str | None, env_path: Path,
             envs_root: Path | None, requested_version: str,
             snapshot: Path | None = None) -> None:
    python_path = venv_python(env_path)
    if not python_path.exists():
        fail(f"No se encontro el interprete en '{python_path}'.")

    resolved = interpreter_version(python_path)

    step("Escribiendo .ai/env.json (portable)")
    write_env_file(uses_python=True, mode=mode, env_name=env_name,
                   python_version=requested_version)
    ok(str(ENV_FILE))

    step("Escribiendo .ai/env.local.json (esta maquina)")
    write_local_file(env_path=env_path, python_path=python_path,
                     envs_root=envs_root, python_version=requested_version,
                     resolved_version=resolved)
    ok(str(LOCAL_FILE))

    step("Actualizando .vscode/settings.json")
    update_vscode_settings(python_path, env_path, envs_root)
    ok(str(SETTINGS_FILE))

    install_dependencies(python_path, env_path, snapshot)

    print()
    print("Ambiente configurado.")
    print(f"  Interprete : {python_path}")
    print(f"  Version    : {resolved or 'desconocida'}  (pedida: {requested_version})")
    print()
    print("Recarga VS Code:  Ctrl+Shift+P -> Developer: Reload Window")
    print()


# -------------------------------------------------------------------- acciones

def confirm_shared_rebuild(name: str | None, env_path: Path, assume_yes: bool) -> None:
    """Un ambiente compartido puede estar en uso por otros proyectos."""
    if assume_yes:
        return
    print()
    print(f"CUIDADO: el ambiente '{name}' es COMPARTIDO y vive en {env_path}")
    print("Si otros proyectos de este computador lo usan, tambien les cambia a ellos.")
    if not sys.stdin.isatty():
        fail("Sin terminal interactiva no se puede confirmar. Pasa --yes si estas seguro.")
    answer = ask("Escribe 'si' para continuar: ").strip().lower()
    if answer not in ("si", "s", "yes", "y"):
        fail("Cancelado. No se modifico nada.")


def action_none() -> None:
    step("Registrando el proyecto como 'sin Python'")
    write_env_file(uses_python=False, mode="none", env_name=None, python_version=None)
    write_local_file(env_path=None, python_path=None, envs_root=None,
                     python_version=None, resolved_version=None)
    update_vscode_settings(None, None, None)
    ok("Los agentes de IA no volveran a preguntar por Python.")


def action_local(python_version: str, force: bool) -> None:
    validate_python_version(python_version)
    env_path = PROJECT_ROOT / ".venv"
    snapshot = snapshot_packages(env_path) if force and is_valid_venv(env_path) else None
    ensure_venv(env_path, python_version, force)
    finalize("local", None, env_path, None, python_version, snapshot)


def action_shared_new(name: str, python_version: str, envs_root: Path,
                      force: bool, assume_yes: bool = False) -> None:
    validate_env_name(name)
    validate_python_version(python_version)
    name = name.strip()
    env_path = envs_root / name

    snapshot = None
    if env_path.exists():
        if not force:
            fail(f"Ya existe '{env_path}'.\n"
                 "Usa --mode shared-existing para reutilizarlo, otro nombre, o --force.")
        confirm_shared_rebuild(name, env_path, assume_yes)
        snapshot = snapshot_packages(env_path)

    envs_root.mkdir(parents=True, exist_ok=True)
    create_venv(env_path, python_version)
    finalize("shared", name, env_path, envs_root, python_version, snapshot)


def action_shared_existing(name: str, envs_root: Path) -> None:
    validate_env_name(name)
    name = name.strip()
    env_path = envs_root / name
    if not is_valid_venv(env_path):
        disponibles = format_env_list(list_existing_envs(envs_root))
        fail(f"No hay un ambiente valido en '{env_path}'.\nDisponibles: {disponibles}")
    step("Reutilizando ambiente existente")
    ok(str(env_path))
    # Se guarda la serie, no el parche: otra maquina no tiene por que tener
    # exactamente el mismo 3.12.8.
    version = python_series(version_from_cfg(env_path) or requested_python_version(None))
    finalize("shared", name, env_path, envs_root, version)


def action_switch_python(new_version: str, assume_yes: bool) -> None:
    """
    Cambia la version de Python del ambiente que ya usa el proyecto.

    Mantiene el mismo modo, el mismo nombre y la misma carpeta. Es la salida
    cuando aparece un problema de compatibilidad a mitad del trabajo.
    """
    validate_python_version(new_version)
    new_version = new_version.strip()

    spec = read_json(ENV_FILE)
    local = read_json(LOCAL_FILE)
    if spec is None:
        fail("Este proyecto todavia no tiene ambiente. Ejecuta el script sin argumentos.")
        return
    if not spec.get("usesPython", True):
        fail("El proyecto esta marcado como 'sin Python'. Usa --change para reconfigurarlo.")
    if local is None or not local.get("envPath"):
        fail("El ambiente no esta resuelto en esta maquina.\n"
             "Ejecuta primero: uv run --script .ai/setup_env.py --sync")
        return

    env_path = Path(local["envPath"])
    mode = spec.get("mode")
    name = spec.get("envName")
    current = local.get("pythonVersionResolved") or local.get("pythonVersion") or "?"

    print()
    print(f"Ambiente : {env_path}")
    print(f"Version  : {current}  ->  {new_version}")

    if mode == "shared":
        confirm_shared_rebuild(name, env_path, assume_yes)

    snapshot = snapshot_packages(env_path)
    envs_root = Path(local["envsRoot"]) if local.get("envsRoot") else None
    create_venv(env_path, new_version)
    finalize(mode or "local", name, env_path, envs_root, new_version, snapshot)


def action_sync(envs_root_cli: str | None, force: bool) -> None:
    """Materializa el ambiente en una maquina nueva a partir de .ai/env.json."""
    spec = read_json(ENV_FILE)
    if spec is None:
        fail("No existe .ai/env.json (o esta corrupto). "
             "Ejecuta el script sin --sync para configurarlo.")
        return

    schema = spec.get("schemaVersion", 0)
    if schema > SCHEMA_VERSION:
        warn(f".ai/env.json usa el esquema {schema} y este script entiende hasta "
             f"{SCHEMA_VERSION}. Actualiza la plantilla si algo falla.")
    elif schema < MIN_SUPPORTED_SCHEMA:
        fail(f".ai/env.json usa un esquema antiguo ({schema}). Reconfigura con --force.")

    if not spec.get("usesPython", True):
        ok("El proyecto esta marcado como 'sin Python'. Nada que hacer.")
        write_local_file(env_path=None, python_path=None, envs_root=None,
                         python_version=None, resolved_version=None)
        update_vscode_settings(None, None, None)
        return

    version = spec.get("pythonVersion") or requested_python_version(None)
    mode = spec.get("mode")

    if mode == "local":
        env_path = PROJECT_ROOT / ".venv"
        ensure_venv(env_path, version, force)
        finalize("local", None, env_path, None, version)
        return

    if mode == "shared":
        name = spec.get("envName")
        if not name:
            fail(".ai/env.json tiene mode 'shared' pero no tiene envName.")
        envs_root = resolve_envs_root(envs_root_cli)
        env_path = envs_root / name
        envs_root.mkdir(parents=True, exist_ok=True)
        ensure_venv(env_path, version, force)
        finalize("shared", name, env_path, envs_root, version)
        return

    fail(f"Modo desconocido en .ai/env.json: {mode!r}")


def action_show(envs_root_cli: str | None) -> None:
    print()
    print(f"Proyecto            : {PROJECT_ROOT}")
    print(f"Config de la maquina: {machine_config_path()}")
    root = resolve_envs_root(envs_root_cli, allow_prompt=False)
    print(f"Carpeta de ambientes: {root}")
    print(f"Ambientes ahi       : {format_env_list(list_existing_envs(root))}")
    print(f"Python por defecto  : {requested_python_version(None)} "
          f"({python_version_source(None)})")
    instaladas = installed_python_versions()
    if instaladas:
        print(f"Python instalado    : {', '.join(instaladas)}")
    print()
    for label, path in (("env.json (portable)", ENV_FILE), ("env.local.json", LOCAL_FILE)):
        data = read_json(path)
        print(f"{label}:")
        print(json.dumps(data, indent=2) if data else "  (no existe)")
        print()


def action_agent_context() -> None:
    """Bloque corto y deterministico para inyectar en el contexto de un agente."""
    local = read_json(LOCAL_FILE)
    spec = read_json(ENV_FILE)

    print("=== Ambiente de Python del proyecto (ai-python-bootstrap) ===")

    if local is not None:
        python_path = local.get("pythonPath")
        if python_path is None:
            print("Estado: SIN PYTHON. El usuario ya decidio que este proyecto no usa Python.")
            print("Instruccion: no preguntes por ambientes ni crees archivos .py sin pedirlo.")
            return
        if Path(python_path).exists():
            version = local.get("pythonVersionResolved") or local.get("pythonVersion")
            print("Estado: CONFIGURADO. No preguntes nada.")
            print(f"pythonPath: {python_path}")
            print(f"envPath   : {local.get('envPath')}")
            print(f"pythonVersion: {version}")
            print('Instruccion: usa uv pasando --python "<pythonPath>" en cada comando.')
            print('  uv pip install --python "<pythonPath>" <paquete>')
            print("Si el usuario pide cambiar de ambiente o de version de Python, no")
            print("edites nada a mano; ejecuta uno de estos y confirma el resultado:")
            print("  uv run --script .ai/setup_env.py --switch-python <version>")
            print("  uv run --script .ai/setup_env.py --change")
            return
        print("Estado: ROTO. El interprete registrado ya no existe.")
        print("Instruccion: ejecuta 'uv run --script .ai/setup_env.py --sync'. No preguntes.")
        return

    if spec is not None:
        print("Estado: DECISION TOMADA, SIN RESOLVER EN ESTA MAQUINA.")
        print(f"mode: {spec.get('mode')}   envName: {spec.get('envName')}")
        print("Instruccion: ejecuta 'uv run --script .ai/setup_env.py --sync'. No preguntes.")
        return

    print("Estado: SIN CONFIGURAR (primera vez).")
    print("Instruccion: antes de ejecutar Python o instalar dependencias, PREGUNTA al")
    print("usuario cual de estas cuatro opciones quiere y espera su respuesta:")
    print("  1. Ambiente local .venv dentro del proyecto")
    print("  2. Ambiente nuevo en la carpeta central de este computador (pide el nombre)")
    print("  3. Ambiente existente de la carpeta central (muestra la lista con --show)")
    print("  4. Sin Python")
    print()
    print("Si elige 1 o 2, PREGUNTA TAMBIEN la version de Python.")
    print(f"  Por defecto: {requested_python_version(None)} ({python_version_source(None)})")
    instaladas = installed_python_versions()
    if instaladas:
        print(f"  Ya instaladas aqui: {', '.join(instaladas)}")
    print("  Si elige la 3, la version la manda el ambiente que ya existe: no preguntes.")
    print()
    print("Luego ejecuta:")
    print("  uv run --script .ai/setup_env.py --mode <...> --python-version <version>")


# ----------------------------------------------------------------- interactivo

def interactive_menu(envs_root_cli: str | None,
                     python_version_cli: str | None) -> tuple[str, str | None, str | None]:
    """Devuelve (modo, nombre, version). La version es None si no aplica."""
    if not sys.stdin.isatty():
        fail("No hay terminal interactiva. Pasa --mode local | shared-new | "
             "shared-existing | none.")

    envs_root = resolve_envs_root(envs_root_cli)
    existing = list_existing_envs(envs_root)
    suggested = requested_python_version(python_version_cli)
    source = python_version_source(python_version_cli)

    print()
    print(f"Configuracion del ambiente de Python para: {PROJECT_ROOT.name}")
    print()
    print(f"  1) Ambiente LOCAL          -> {PROJECT_ROOT / '.venv'}")
    print(f"  2) Ambiente NUEVO en       -> {envs_root}")
    print(f"  3) Ambiente EXISTENTE en   -> {envs_root}  ({len(existing)} disponibles)")
    print("  4) Sin Python")
    print()

    choice = ask("Selecciona una opcion [1-4]: ").strip()

    if choice == "1":
        return "local", None, prompt_python_version(suggested, source)
    if choice == "2":
        default = PROJECT_ROOT.name
        name = ask(f"Nombre del ambiente [{default}]: ").strip() or default
        return "shared-new", name, prompt_python_version(suggested, source)
    if choice == "3":
        if not existing:
            fail(f"No hay ambientes en {envs_root}. Usa la opcion 2 para crear uno.")
        print()
        for i, (name, version) in enumerate(existing, start=1):
            print(f"  {i}) {name}  (Python {version})")
        print()
        sel = ask(f"Selecciona el ambiente [1-{len(existing)}]: ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(existing)):
            fail("Seleccion invalida.")
        # La version la manda el ambiente que ya existe; no se pregunta.
        return "shared-existing", existing[int(sel) - 1][0], None
    if choice == "4":
        return "none", None, None

    fail("Seleccion invalida.")
    raise SystemExit(1)


# ------------------------------------------------------------------------ main

def run_mode(mode: str, name: str | None, version_cli: str | None,
             envs_root_cli: str | None, force: bool, assume_yes: bool) -> None:
    require_uv()
    version = requested_python_version(version_cli)

    if mode == "local":
        action_local(version, force)
    elif mode == "shared-new":
        if not name:
            fail("El modo 'shared-new' requiere --name.")
            return
        action_shared_new(name, version, resolve_envs_root(envs_root_cli),
                          force, assume_yes)
    elif mode == "shared-existing":
        if not name:
            fail("El modo 'shared-existing' requiere --name.")
            return
        action_shared_existing(name, resolve_envs_root(envs_root_cli))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configura el ambiente de Python del proyecto con uv.")
    parser.add_argument("--mode", choices=["local", "shared-new", "shared-existing", "none"])
    parser.add_argument("--name", help="Nombre del ambiente compartido.")
    parser.add_argument("--python-version", dest="python_version",
                        help='Version de Python a usar, p.ej. "3.12" o "3.12.8".')
    parser.add_argument("--envs-root", dest="envs_root",
                        help="Carpeta de ambientes solo para esta ejecucion.")
    parser.add_argument("--sync", action="store_true",
                        help="Materializa el ambiente en esta maquina desde .ai/env.json.")
    parser.add_argument("--show", action="store_true",
                        help="Muestra la configuracion actual.")
    parser.add_argument("--agent-context", dest="agent_context", action="store_true",
                        help="Imprime el estado en formato corto para un agente de IA.")

    cambiar = parser.add_argument_group("cambiar de opinion a mitad del trabajo")
    cambiar.add_argument("--change", action="store_true",
                         help="Vuelve a abrir el menu para elegir otro ambiente.")
    cambiar.add_argument("--switch-python", dest="switch_python", metavar="VERSION",
                         help="Rehace el ambiente actual con otra version de Python.")
    cambiar.add_argument("--force", action="store_true",
                         help="Rehace el ambiente aunque ya exista.")
    cambiar.add_argument("--yes", action="store_true",
                         help="No pide confirmacion al rehacer un ambiente compartido.")

    maquina = parser.add_argument_group("ajustes de este computador")
    maquina.add_argument("--set-envs-root", dest="set_envs_root", metavar="RUTA",
                         help="Guarda la carpeta de ambientes de este computador y sale.")
    maquina.add_argument("--set-default-python", dest="set_default_python",
                         metavar="VERSION",
                         help="Guarda la version de Python por defecto y sale.")

    args = parser.parse_args()

    if args.agent_context:
        action_agent_context()
        return

    if args.set_envs_root:
        root = Path(args.set_envs_root).expanduser()
        path = write_machine_config({**read_machine_config(), "envsRoot": str(root)})
        print(f"Carpeta de ambientes de este computador: {root}")
        print(f"Guardado en: {path}")
        return

    if args.set_default_python:
        validate_python_version(args.set_default_python)
        version = args.set_default_python.strip()
        path = write_machine_config(
            {**read_machine_config(), "defaultPythonVersion": version})
        print(f"Version de Python por defecto de este computador: {version}")
        print(f"Guardado en: {path}")
        print("Solo afecta a los ambientes que se creen de aqui en adelante.")
        return

    if args.show:
        action_show(args.envs_root)
        return

    if args.sync:
        require_uv()
        action_sync(args.envs_root, args.force)
        return

    if args.switch_python:
        require_uv()
        action_switch_python(args.switch_python, args.yes)
        return

    force = args.force or args.change

    # Ya hay decision resuelta en esta maquina y no se pide reconfigurar.
    if LOCAL_FILE.exists() and not force and not args.mode:
        local = read_json(LOCAL_FILE) or {}
        python_path = local.get("pythonPath")
        if python_path is None or Path(python_path).exists():
            print("\nEste proyecto ya esta configurado:")
            print(json.dumps(local, indent=2))
            print("\nPara cambiar de ambiente : --change")
            print("Para cambiar de version   : --switch-python 3.11")
            print("Para rehacerlo aqui       : --sync\n")
            return
        print("\nAviso: el interprete registrado ya no existe. Se vuelve a resolver.\n")
        require_uv()
        action_sync(args.envs_root, force=True)
        return

    # Proyecto clonado en una maquina nueva: hay env.json pero no env.local.json.
    if ENV_FILE.exists() and not LOCAL_FILE.exists() and not args.mode and not args.change:
        step("Se encontro .ai/env.json sin resolver en esta maquina")
        require_uv()
        action_sync(args.envs_root, args.force)
        return

    mode, name, version = args.mode, args.name, args.python_version
    if not mode:
        mode, name, version = interactive_menu(args.envs_root, args.python_version)

    if mode == "none":
        action_none()
        return

    run_mode(mode, name, version, args.envs_root, force, args.yes)


if __name__ == "__main__":
    main()
