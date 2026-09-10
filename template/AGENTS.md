# Instrucciones para agentes de IA

Este archivo es la **fuente única de verdad** para cualquier asistente de IA que
trabaje en este proyecto: Claude Code, GitHub Copilot, Codex, Cursor, Windsurf,
Gemini CLI y demás.

---

## 1. Regla de arranque: ambiente de Python

**Antes de ejecutar Python, instalar dependencias o crear archivos `.py`, revisa
la carpeta `.ai/`.** Hay dos archivos y significan cosas distintas:

| Archivo | Qué es | ¿En git? |
|---|---|---|
| `.ai/env.json` | La decisión del proyecto. Portable, sin rutas absolutas. | Sí |
| `.ai/env.local.json` | Rutas resueltas para **este** computador. | No |

Si tu herramienta puede ejecutar comandos, la forma más rápida de saber en qué
estado estás es pedirle el resumen al propio script:

```bash
uv run --script .ai/setup_env.py --agent-context
```

Imprime el estado y la instrucción exacta que debes seguir. Si no puedes
ejecutar comandos, aplica el árbol de decisión de abajo.

### A. Existe `.ai/env.local.json`

Todo listo. Usa el intérprete del campo `pythonPath`. **No preguntes nada.**
Si el archivo dice `"pythonPath": null`, el proyecto no usa Python.

### B. Existe `.ai/env.json` pero no `.ai/env.local.json`

El proyecto viene de otro computador (recién clonado). La decisión ya está
tomada: **no vuelvas a preguntar**. Solo materialízala aquí:

```bash
uv run --script .ai/setup_env.py --sync
```

Si la carpeta de ambientes no está definida en este computador, el script lo
preguntará él mismo. Deja que lo haga.

### C. No existe ninguno de los dos

Primera vez. **Detente y hazle al usuario esta pregunta, con estas cuatro
opciones:**

> Este proyecto todavía no tiene un ambiente de Python configurado. ¿Qué prefieres?
>
> 1. **Ambiente virtual local** — crear `.venv` dentro de la carpeta del proyecto.
> 2. **Ambiente nuevo en la carpeta central de este computador** — dime el nombre
>    que quieres darle.
> 3. **Ambiente existente** — reutilizar uno de la carpeta central. Dime cuál.
> 4. **Sin Python** — este proyecto no usa Python.

Espera la respuesta. No asumas una opción por defecto. Para las opciones 2 y 3,
muestra primero cuál es la carpeta central de este computador y qué hay dentro:

```bash
uv run --script .ai/setup_env.py --show
```

**Si elige la opción 1 o la 2, pregúntale también qué versión de Python quiere.**
El comando anterior imprime la versión por defecto de este computador y las que
ya están instaladas: ofrécelas como sugerencia y deja claro que uv descarga
cualquier otra si hace falta. Con la opción 3 no preguntes: la versión la manda
el ambiente que ya existe.

### Ejecuta el script; no crees el ambiente a mano

```bash
uv run --script .ai/setup_env.py --mode local --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-new --name "mi-proyecto" --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-existing --name "mi-proyecto"
uv run --script .ai/setup_env.py --mode none
```

Si omites `--python-version`, el script usa la versión por defecto sin
preguntar. Pásala siempre que el usuario te haya dado una.

En Windows también sirve `.ai\setup-env.ps1` con los mismos argumentos; en
macOS y Linux, `.ai/setup-env.sh`.

El script crea el ambiente con `uv`, escribe los dos archivos de `.ai/` y
actualiza `.vscode/settings.json`. Después de ejecutarlo, confirma al usuario la
ruta resultante y sigue con la tarea original.

---

## 2. Cambiar de ambiente o de versión a mitad del trabajo

Si aparece un problema de compatibilidad (un paquete que no soporta la versión
instalada, una librería que exige otra), el usuario puede pedir el cambio en
cualquier momento. **No edites `.ai/env.json` ni `.ai/env.local.json` a mano, y
no crees ambientes por tu cuenta.** Usa uno de estos tres comandos:

| Lo que pide el usuario | Comando |
|---|---|
| "cambia a Python 3.11" | `uv run --script .ai/setup_env.py --switch-python 3.11` |
| "quiero otro ambiente" | `uv run --script .ai/setup_env.py --change` |
| "usa el ambiente `otro`" | `uv run --script .ai/setup_env.py --mode shared-existing --name "otro"` |

`--switch-python` conserva el modo, el nombre y la carpeta del ambiente: solo
cambia el intérprete. Antes de rehacerlo anota los paquetes instalados en
`.ai/packages.backup.txt` y los reinstala después. Si el proyecto tiene
`pyproject.toml` o `requirements.txt`, esos mandan sobre la copia.

Dos advertencias que debes trasladarle al usuario antes de ejecutar nada:

- Si el ambiente es **compartido**, cambiarle la versión afecta a todos los
  proyectos de este computador que lo usen. El script pide confirmación por
  terminal; si no la hay, falla salvo que pases `--yes`. **No pases `--yes` sin
  que el usuario lo haya autorizado explícitamente.**
- Al reinstalar los paquetes en la versión nueva, algunos pueden no tener
  compatibilidad. El script avisa y deja la lista en `.ai/packages.backup.txt`.

Después de cualquiera de estos comandos, vuelve a leer `pythonPath` de
`.ai/env.local.json`: cambió el intérprete y los comandos anteriores ya no
sirven.

---

## 3. Nunca escribas rutas de ambientes en el código ni en la documentación

La carpeta de ambientes cambia de un computador a otro. **No hardcodees**
`C:\PythonFiles\envs` ni ninguna otra ruta en scripts, README, CI o ejemplos.
Si necesitas la ruta, léela de `.ai/env.local.json` en tiempo de ejecución.

Para cambiar la carpeta de ambientes de este computador:

```bash
uv run --script .ai/setup_env.py --set-envs-root "D:/envs"
```

---

## 4. Gestor de paquetes: siempre `uv`

- **Nunca** uses `python -m venv`, `virtualenv`, `conda` ni `pyenv`.
- **Nunca** uses `pip install` sobre el Python del sistema.

| Tarea | Comando |
|---|---|
| Instalar un paquete | `uv pip install --python "<pythonPath>" <paquete>` |
| Instalar desde requirements | `uv pip install --python "<pythonPath>" -r requirements.txt` |
| Listar paquetes | `uv pip list --python "<pythonPath>"` |
| Congelar dependencias | `uv pip freeze --python "<pythonPath>" > requirements.txt` |
| Ejecutar un script | `uv run --python "<pythonPath>" script.py` |

Toma `<pythonPath>` del campo homónimo de `.ai/env.local.json`. Pasar `--python`
explícitamente evita que `uv` cree un `.venv` paralelo cuando el ambiente vive
fuera del proyecto.

Si el proyecto usa `pyproject.toml` con `uv sync` / `uv add`, la variable
`UV_PROJECT_ENVIRONMENT` ya queda configurada en `.vscode/settings.json`, así
que esos comandos apuntan al ambiente correcto desde la terminal de VS Code.

---

## 5. Formato de los archivos

`.ai/env.json` — portable, se versiona:

```json
{
  "schemaVersion": 3,
  "usesPython": true,
  "mode": "shared",
  "envName": "analitica",
  "pythonVersion": "3.12",
  "manager": "uv"
}
```

`mode` es `local`, `shared` o `none`. `envName` solo aplica cuando es `shared`.
`pythonVersion` es la **serie pedida**, no la versión exacta instalada: así el
mismo archivo funciona en máquinas donde uv resuelve un parche distinto.

`.ai/env.local.json` — específico del computador, no se versiona:

```json
{
  "schemaVersion": 3,
  "envPath": "/ruta/a/envs/analitica",
  "pythonPath": "/ruta/a/envs/analitica/bin/python",
  "envsRoot": "/ruta/a/envs",
  "pythonVersion": "3.12",
  "pythonVersionResolved": "3.12.3",
  "platform": "linux"
}
```

Si `pythonPath` apunta a una ruta que ya no existe, ejecuta
`uv run --script .ai/setup_env.py --sync` para reconstruir el ambiente. **No
edites estos archivos a mano.**

---

## 6. Convenciones generales del proyecto

<!-- Personaliza esta sección por proyecto -->

- Estilo de código: `ruff` para lint y formato.
- No hagas commit de `.venv/`, `.ai/env.local.json` ni de archivos con secretos.
- Antes de proponer una dependencia nueva, revisa si ya está en el ambiente.
