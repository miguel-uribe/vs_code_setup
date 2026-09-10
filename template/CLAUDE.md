# CLAUDE.md

Las instrucciones de este proyecto viven en `AGENTS.md`. Se importan aquí:

@AGENTS.md

## Recordatorio prioritario

Antes de cualquier comando de Python, revisa `.ai/`:

- `env.local.json` existe → usa `pythonPath`. No preguntes.
- Solo `env.json` → `uv run --script .ai/setup_env.py --sync`. No preguntes.
- Ninguno → pregunta las 4 opciones de `AGENTS.md` **y la versión de Python**
  (esto último solo para las opciones 1 y 2), luego ejecuta el script.

Si a mitad del trabajo hay un problema de compatibilidad, el cambio se pide con
`--switch-python <version>` o con `--change`. Nunca edites los archivos de
`.ai/` a mano.

El hook `SessionStart` de `.claude/settings.json` ya imprime este estado al
abrir la sesión. Si no lo ves, pídelo tú:

```bash
uv run --script .ai/setup_env.py --agent-context
```

Ambientes solo con `uv`. Nunca hardcodees rutas de ambientes.
