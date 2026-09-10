# Instrucciones para GitHub Copilot

Las reglas completas están en `AGENTS.md` en la raíz del repositorio. Lo
esencial:

## Ambiente de Python

Antes de ejecutar Python, instalar dependencias o crear archivos `.py`, revisa
la carpeta `.ai/`:

1. **Existe `.ai/env.local.json`** → usa su campo `pythonPath`. No preguntes nada.
2. **Existe `.ai/env.json` pero no `.ai/env.local.json`** → el proyecto se clonó
   en este computador. No preguntes; ejecuta `uv run --script .ai/setup_env.py --sync`.
3. **No existe ninguno** → pregunta al usuario y espera su respuesta:
   - Ambiente virtual local (`.venv` en el proyecto).
   - Ambiente nuevo en la carpeta central del computador (pide el nombre).
   - Ambiente existente en la carpeta central (pide cuál).
   - Sin Python.

Con las dos primeras opciones pregunta **también la versión de Python**. Con la
tercera no: la manda el ambiente que ya existe. `--show` imprime la versión por
defecto y las que ya están instaladas en este computador.

Luego ejecuta:

```bash
uv run --script .ai/setup_env.py --mode local --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-new --name "<nombre>" --python-version 3.12
uv run --script .ai/setup_env.py --mode shared-existing --name "<nombre>"
uv run --script .ai/setup_env.py --mode none
```

## Cambiar de ambiente o de versión después

Si aparece un problema de compatibilidad, no edites los archivos de `.ai/` a
mano ni crees ambientes por tu cuenta:

```bash
uv run --script .ai/setup_env.py --switch-python 3.11   # misma carpeta, otra version
uv run --script .ai/setup_env.py --change               # elegir otro ambiente
```

`--switch-python` conserva los paquetes: los anota antes y los reinstala
después. Si el ambiente es compartido, el cambio afecta a los demás proyectos
que lo usen y el script pide confirmación. Después vuelve a leer `pythonPath`,
porque cambió.

Atajo para saber el estado actual sin leer archivos:

```bash
uv run --script .ai/setup_env.py --agent-context
```

Para ver la carpeta central de este computador y los ambientes disponibles:
`uv run --script .ai/setup_env.py --show`

## Reglas fijas

- Gestor de paquetes: **siempre `uv`**. Nunca `python -m venv`, `virtualenv`,
  `conda` ni `pip` directo.
- `uv pip install --python "<pythonPath>" <paquete>`, tomando `<pythonPath>` de
  `.ai/env.local.json`.
- **Nunca escribas rutas absolutas de ambientes** en el código o la
  documentación: cambian de un computador a otro.
