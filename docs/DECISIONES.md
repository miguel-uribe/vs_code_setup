# Decisiones de diseño

Notas sobre por qué la plantilla está hecha así, y qué cambió respecto de la
versión anterior (`ai-python-bootstrap.zip`).

## Por qué tres capas y no una

Un solo archivo de configuración obligaría a elegir entre dos cosas
incompatibles: versionar la decisión en git (para que el equipo la comparta) y
guardar rutas absolutas (para que la máquina sepa dónde está el intérprete). Las
rutas absolutas no sobreviven al cambio de computador.

La separación resuelve el conflicto:

- `.ai/env.json` guarda la **intención** y se versiona.
- `.ai/env.local.json` guarda la **resolución** y se ignora.
- La config de la máquina guarda **dónde vive la carpeta de ambientes**.

De ahí sale la propiedad más importante del sistema: al clonar, el agente sabe
que la decisión ya está tomada y no vuelve a preguntar.

## Por qué la plantilla vive en `template/`

En la versión anterior el instalador copiaba desde la raíz del propio repo, así
que el `.gitignore` y el `.vscode/` del repo eran a la vez los de la plantilla.
Eso hacía imposible que el repo tuviera configuración propia distinta de la que
reparte. Con `template/` la separación es explícita.

El `.gitignore` de la plantilla se llama `_gitignore` en el repo para que git no
lo aplique a los archivos de la plantilla, y el instalador lo escribe con su
nombre real en el destino.

## Por qué un hook de Claude Code

`AGENTS.md` y `CLAUDE.md` son instrucciones: el modelo puede leerlas o no. El
hook `SessionStart` de `.claude/settings.json` ejecuta
`setup_env.py --agent-context` al abrir la sesión e inyecta el estado en el
contexto. Eso convierte "el agente debería preguntar" en "el agente recibe la
instrucción de preguntar". Los archivos de instrucciones siguen ahí como
respaldo, y para los agentes que no soportan hooks.

## Cambios respecto de la versión anterior

### Correcciones

- **`.ai/env.json` guardaba el parche exacto de Python** (`3.12.3`), tomado del
  intérprete recién creado. Al sincronizar en otra máquina, `uv venv --python
  3.12.3` exigía esa versión exacta y podía forzar una descarga innecesaria.
  Ahora se guarda la serie pedida (`3.12`) y el parche resuelto queda solo en el
  archivo local.
- **Si el intérprete no respondía**, se escribía `"pythonVersion": "desconocida"`
  en el archivo versionado, que luego rompía el `--sync`. Ahora la versión de
  `env.json` nunca depende de esa consulta.
- **`--mode none` no limpiaba `UV_PROJECT_ENVIRONMENT`** de la configuración de
  terminal. Un proyecto marcado como "sin Python" se quedaba apuntando al
  ambiente anterior. Ahora se limpia junto con las demás claves.
- **`settings.json` con comentarios se descartaba.** VS Code acepta JSONC, pero
  el script hacía `json.loads` directo, fallaba, respaldaba el archivo y escribía
  uno vacío, perdiendo la configuración del usuario. Ahora se quitan comentarios
  y comas colgantes antes de interpretar.
- **`--mode local` recreaba `.venv`** aunque ya existiera uno válido. Ahora se
  reutiliza salvo que se pase `--force`.
- **El menú interactivo se colgaba sin terminal.** Ahora falla con un mensaje que
  indica qué `--mode` pasar.
- Escritura atómica de todos los JSON, para no dejar archivos a medias si el
  proceso muere.

### Añadidos

- `--agent-context`: estado del ambiente en formato corto para agentes, con la
  instrucción exacta a seguir en cada caso.
- El instalador **fusiona** `settings.json`, `tasks.json`, `extensions.json` y
  `.claude/settings.json` en lugar de omitirlos cuando ya existen, y a
  `.gitignore` solo le agrega las líneas que faltan.
- `--dry-run` en el instalador.
- Soporte de `pyproject.toml`: si existe, se usa `uv sync` con
  `UV_PROJECT_ENVIRONMENT` apuntando al ambiente correcto, en vez de
  `requirements.txt`.
- `python.venvPath` en `settings.json` cuando el ambiente es compartido, para que
  el selector de intérprete de VS Code liste la carpeta central.
- La lista de ambientes existentes muestra la versión de Python de cada uno,
  leída de `pyvenv.cfg` sin lanzar el intérprete.
- `.vscode/extensions.json` con las extensiones recomendadas.

## Elección de versión de Python

La versión se pregunta solo cuando la respuesta cambia algo. Al crear un
ambiente (local o compartido nuevo) se pregunta; al reutilizar uno existente no,
porque la versión ya está decidida por ese ambiente y preguntarla sería ofrecer
una opción falsa.

La sugerencia sale de una cadena de cuatro fuentes, de la más específica a la
más general, y el menú dice de cuál vino (`por defecto de este computador`, `del
archivo .python-version`). Ver de dónde sale un valor evita la pregunta de por
qué salió ese y no otro.

`.python-version` va antes que la config del computador a propósito: es un
archivo del proyecto, y además es el estándar que ya leen uv y pyenv, así que un
proyecto que lo tenga funciona sin configuración extra.

## Cambiar de ambiente o de versión sobre la marcha

Un problema de compatibilidad aparece a mitad del trabajo, cuando el ambiente ya
tiene paquetes instalados. Rehacerlo con otra versión de Python los borraría, así
que `--switch-python` los anota con `uv pip freeze` antes y los reinstala
después. La copia queda en `.ai/packages.backup.txt` aunque la reinstalación
falle, que es justo el caso en que el usuario la necesita.

El orden de precedencia al restaurar es `pyproject.toml`, luego
`requirements.txt`, y solo si no hay ninguno, la copia. Las dependencias
declaradas son la fuente de verdad; la copia es una red de seguridad para los
paquetes que alguien instaló a mano.

Se separaron dos comandos en vez de uno solo:

- `--switch-python` conserva modo, nombre y carpeta. Solo cambia el intérprete.
- `--change` reabre el menú completo, para cuando lo que cambia es el ambiente.

Cambiar la versión de un ambiente **compartido** afecta a otros proyectos del
mismo computador, así que ese caso pide confirmación explícita. `--yes` existe
para scripts, y `AGENTS.md` prohíbe a los agentes usarla sin permiso del usuario:
un agente que la pasara por su cuenta podría romper el trabajo de otro proyecto
sin que nadie se enterara.

## Dos fallos que solo aparecieron al probar

- **`uv venv` no pisa un ambiente existente.** Desde uv 0.12 hace falta
  `--clear`. Sin eso, tanto `--force` como `--switch-python` fallaban al llegar a
  la carpeta ocupada. El script añade la bandera solo cuando la carpeta ya
  existe.
- **`isatty()` miente.** En terminales de agentes y de CI puede decir que hay
  entrada interactiva y luego dar EOF en la primera lectura, con lo que el
  script moría con un traceback en mitad de una confirmación. Ahora todas las
  preguntas pasan por un `ask()` que convierte EOF y Ctrl+C en un mensaje que
  dice qué bandera usar.

También quedó a la vista que `pyvenv.cfg` guarda `version_info = 3.11` cuando se
pidió la serie y no el parche, así que la versión resuelta solo se toma de ahí
si trae los tres números; si no, se le pregunta al intérprete.

## Limitaciones conocidas

- Al fusionar `settings.json`, **los comentarios del archivo original se
  pierden**: la salida es JSON limpio. El contenido se conserva.
- El hook de Claude Code requiere aprobación del usuario la primera vez.
- `--set-envs-root` escribe en la configuración del computador, fuera del
  proyecto. Es intencional, pero conviene saberlo antes de ejecutarlo en una
  máquina compartida.
- Al reinstalar paquetes tras cambiar de versión, `uv pip freeze` produce
  versiones fijadas. Alguna puede no tener build para el Python nuevo. El script
  avisa y conserva la lista, pero no intenta resolver el conflicto.
- No hay pruebas automatizadas. La verificación fue manual sobre proyectos de
  prueba, cubriendo: instalación limpia, instalación sobre configuración
  existente, los cuatro modos, clonado a otra carpeta de ambientes, recuperación
  tras borrar el intérprete, las cuatro ramas del menú de versión, cambio de
  versión con paquetes instalados, cambio a una versión no instalada, y la
  confirmación del ambiente compartido con y sin `--yes`.

## Cobertura de los cinco agentes de VS Code

El objetivo es que Claude Code, GitHub Copilot, OpenAI Codex y Gemini se
comporten igual dentro de VS Code. Cada uno lee un archivo distinto, así que
`AGENTS.md` sigue siendo la fuente única y los demás archivos son puentes hacia
él. Lo que hubo que resolver:

- **Copilot ignoraba `AGENTS.md`.** VS Code trae `chat.useAgentsMdFile` apagado
  por ser experimental, así que el archivo central no llegaba al contexto y
  Copilot se quedaba solo con `.github/copilot-instructions.md`. La plantilla lo
  enciende en `.vscode/settings.json`. Si el proyecto ya lo tenía en `false`, el
  instalador respeta ese valor: hay que pasar `--force`.
- **Gemini recibía un resumen incompleto.** El puente genérico no mencionaba
  `--switch-python` ni `--change`, así que Gemini no sabía cómo cambiar de
  ambiente y podía inventarse el procedimiento. Ahora `GEMINI.md` abre con
  `@AGENTS.md`, que la CLI resuelve como importación, y debajo repite lo
  esencial porque la extensión de VS Code no garantiza resolverla.
- **`.gemini/settings.json`** declara `context.fileName` con `AGENTS.md` y
  `GEMINI.md`. Es la vía soportada para que la CLI lea el archivo estándar sin
  depender de la importación. Se fusiona en lugar de sobrescribirse, y los
  nombres que el proyecto ya tuviera se conservan.
- **Codex no necesita puente.** `AGENTS.md` en la raíz es su formato nativo.
- **Las extensiones se recomiendan.** `.vscode/extensions.json` lista los cinco
  asistentes, así que al abrir el proyecto VS Code los ofrece.

Solo Claude Code tiene una garantía determinista, porque es el único con hooks.
Para los otros tres, la instrucción escrita es todo lo que hay: se puede hacer
que el archivo sea fácil de encontrar y difícil de malinterpretar, pero no que
el modelo esté obligado a seguirlo.
