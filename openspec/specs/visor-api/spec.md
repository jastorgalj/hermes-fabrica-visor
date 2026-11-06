# visor-api Specification

## Purpose
API HTTP de solo lectura que expone los datos del tablero kanban local para consumo del visor de flujo. La ruta de la DB se detecta en orden: variable de entorno `KANBAN_DB`, luego `%LOCALAPPDATA%\hermes\kanban.db` (Windows), luego `~/.hermes/kanban.db`; si ninguna existe, el servidor sale con mensaje claro. Permite separar la capa de datos de la UI para facilitar migrar la UI a otro consumidor en el futuro.

## Requirements

### Requirement: Inicio en interfaz local exclusiva
El servidor SHALL iniciarse ligado unicamente a `127.0.0.1` en el puerto configurado (por defecto 8787) y MUST nunca escuchar en `0.0.0.0` ni en ninguna otra interfaz de red.

#### Scenario: Inicio en interfaz local
WHEN el servidor arranca
THEN el socket queda ligado a `127.0.0.1:<puerto>` y una petición a `0.0.0.0:<puerto>` no es aceptada por el servidor

### Requirement: Deteccion de ruta de base de datos
El servidor SHALL detectar la ruta de `kanban.db` en este orden: (1) variable de entorno `KANBAN_DB` si está definida; (2) `%LOCALAPPDATA%\hermes\kanban.db` si `LOCALAPPDATA` está definido (Windows); (3) `~/.hermes/kanban.db`; si ninguna ruta existe, MUST salir con un mensaje claro que liste las rutas probadas, sin lanzar un traceback.

#### Scenario: Variable de entorno KANBAN_DB definida
WHEN la variable de entorno `KANBAN_DB` apunta a un archivo existente
THEN el servidor abre ese archivo y no consulta ninguna ruta alternativa

#### Scenario: Ruta Windows por defecto
WHEN `KANBAN_DB` no está definida y `LOCALAPPDATA` apunta a `C:\Users\jastorga\AppData\Local`
THEN el servidor intenta abrir `C:\Users\jastorga\AppData\Local\hermes\kanban.db`

#### Scenario: Ninguna ruta existe
WHEN ninguna de las tres rutas apunta a un archivo existente
THEN el servidor imprime un mensaje legible que lista las rutas probadas y sale con código de error no cero, sin traceback de Python

### Requirement: Apertura de DB en modo solo lectura
El servidor MUST abrir `kanban.db` con la URI `file:<ruta>?mode=ro` y la conexion SHALL rechazar cualquier sentencia de escritura (INSERT/UPDATE/DELETE) con `sqlite3.OperationalError`.

#### Scenario: Apertura en modo ro
WHEN el servidor procesa cualquier petición
THEN la conexión SQLite se abre con `uri=True` y `mode=ro`; una sentencia INSERT/UPDATE/DELETE lanza `sqlite3.OperationalError` sin llegar a ejecutarse

### Requirement: Endpoint de grupos
El servidor SHALL responder `GET /api/groups` con un array JSON de objetos
`{key, label, task_count, running_count, blocked_input_count, last_activity}`
donde `key` es el primer token del titulo (separado por espacio o dos puntos),
agrupando todas las tasks con `status != 'archived'`. El campo `last_activity`
SHALL ser el valor máximo de `started_at` de las tasks del grupo (unix epoch,
entero), o `null` si ninguna task del grupo tiene `started_at` no nulo. El array
MUST estar ordenado por `last_activity` DESC nulls last.

#### Scenario: Grupos presentes
WHEN el board tiene tasks con títulos `MTD-357 backend: ...` y `trail-solo-grafo 1/2: ...`
THEN `/api/groups` retorna al menos `[{key:"MTD-357",...},{key:"trail-solo-grafo",...}]` con `task_count >= 1` en cada uno

#### Scenario: Titulo sin patron
WHEN existe una task cuyo título no contiene espacio ni dos puntos
THEN esa task aparece en el grupo con key `(sin-grupo)`

#### Scenario: Orden por actividad reciente
WHEN el board tiene el grupo fabrica-visor con last_activity más reciente que MTD-357
THEN el array retornado por /api/groups tiene fabrica-visor antes que MTD-357,
y cualquier grupo con last_activity = null aparece al final del array

### Requirement: Endpoint de grupo con grafo
El servidor SHALL responder `GET /api/group/{key}` con un objeto JSON `{key, tasks, links}` donde `tasks` incluye todos los campos para renderizar el grafo y el panel de estadisticas, y `links` son los pares `{parent_id, child_id}` del subgrafo interno del grupo.

#### Scenario: Campos de cada task
WHEN se consulta `/api/group/MTD-357`
THEN cada objeto en `tasks` contiene: `id`, `title`, `assignee`, `status`, `block_kind`, `model_override`, `created_at`, `completed_at`, `run_count`, `changes_requested_count`, `failure_count`, `total_duration_seconds`, `runs` (array de `{id, outcome, started_at, ended_at, profile}`)

#### Scenario: Links del subgrafo
WHEN el grupo tiene cards con dependencias entre ellas
THEN `links` contiene pares `{parent_id, child_id}` solo para las cards del grupo (no para links que crucen grupos)

### Requirement: Endpoint de task individual
El servidor SHALL responder `GET /api/tasks/{id}` con el detalle completo de la task incluyendo `comments` y `events` (maximo 50, `kind != 'heartbeat'`, ordenados por `id DESC`), o HTTP 404 si el id no existe.

#### Scenario: Task existente
WHEN se consulta `/api/tasks/t_123` y la task existe
THEN la respuesta incluye todos los campos de task, el array `comments` y el array `events` (máximo 50, ordenados por id descendente)

#### Scenario: Task inexistente
WHEN se consulta `/api/tasks/t_inexistente`
THEN la respuesta es HTTP 404 con body `{"error": "not found"}`

### Requirement: Escape de datos de texto
Los datos de texto provenientes de la DB SHALL llegar al cliente como strings JSON planos; la API MUST serializar con `json.dumps()` que escapa `<`, `>`, `&` automaticamente.

#### Scenario: Datos con HTML
WHEN el título de una task contiene `<script>alert(1)</script>`
THEN la respuesta JSON contiene la string literal `<script>alert(1)</script>` como texto (el escape lo hace el frontend al insertar en el DOM, no la API)

### Requirement: Cabeceras de control de cache
El servidor SHALL incluir `Cache-Control: no-cache` y `Content-Type: application/json` en todas las respuestas de endpoints `/api/*`.

#### Scenario: Cabeceras de respuesta
WHEN se realiza una petición a cualquier endpoint `/api/*`
THEN la respuesta incluye `Cache-Control: no-cache` y `Content-Type: application/json`

### Requirement: Validacion de formato de task_id
El servidor SHALL validar que el parámetro `{id}` en el endpoint
`/api/tasks/{id}/worker-log` coincida con la expresión regular `^t_[0-9a-f]+$`; si
no coincide, MUST responder HTTP 400 con `{"error": "invalid task_id"}` sin construir
ninguna ruta de archivo. Los endpoints `/api/tasks/{id}` y `/api/tasks/{id}/timeline`
resuelven `{id}` directamente contra la base de datos sin validación de formato; si el
id no existe, MUST responder HTTP 404.

#### Scenario: Task id fuera de patron en worker-log
WHEN se consulta `/api/tasks/../../etc/passwd/worker-log`
THEN la respuesta es HTTP 400 con body `{"error": "invalid task_id"}` y no se construye
ninguna ruta de archivo ni se accede al sistema de archivos

#### Scenario: Task id valido en worker-log
WHEN se consulta `/api/tasks/t_4e9a8452/worker-log` y la task existe en la DB
THEN la validación de formato pasa y el servidor construye la ruta del log normalmente

### Requirement: Endpoint de timeline de card
El servidor SHALL responder `GET /api/tasks/{id}/timeline` con
`{task_id, heartbeat_count, truncated, items}`, donde `items` es una lista de items
de tipo run, comentario y evento ordenados por `ts` ascendente (ante empate de `ts`,
por `id` ascendente de la fila de origen). Si `{id}` no existe en la DB, MUST
responder HTTP 404.

#### Scenario: Items mezclados en orden cronologico
WHEN la card `t_3275a989` tiene runs, comentarios y eventos en distintos momentos
THEN `items` está ordenado por `ts` ASC y, ante empate de `ts`, por `id` ASC de
la fila de origen

#### Scenario: Task no encontrada en timeline
WHEN se consulta `/api/tasks/t_00000000/timeline` (id hexadecimal válido, no existe en la DB)
THEN la respuesta es HTTP 404 con body `{"error": "not found"}`

### Requirement: Parametros de filtro de timeline
El parámetro `limit` (entero 1–500, default 200) SHALL limitar el total de items
devueltos por `/api/tasks/{id}/timeline`; si se supera, `truncated` MUST ser `true`.
El parámetro `heartbeats` (bool, default `false`) controla si los events de kind
`heartbeat` se incluyen; `heartbeat_count` SHALL reflejar el total de heartbeats de
la card independientemente del filtro.

#### Scenario: Heartbeats excluidos por defecto con conteo
WHEN se consulta `/api/tasks/{id}/timeline` sin el parámetro `heartbeats`
THEN `items` no contiene ningún item con `kind = "heartbeat"` y `heartbeat_count`
refleja el total real de heartbeats de la card

#### Scenario: Paginacion con limit
WHEN la card tiene 300 items no-heartbeat y se consulta con `limit=200`
THEN `items` tiene exactamente 200 elementos (los primeros cronológicamente) y
`truncated` es `true`

### Requirement: Formato de items en timeline de card
Cada item SHALL incluir `ts` (unix epoch), `type` y `run_id` (nullable). Los runs
generan DOS items: `run_start` (ts = started_at, campo `profile`) y `run_end`
(ts = ended_at, solo si not null; campos `outcome`, `summary` primeros 500 chars y
`metadata_excerpt` con claves `verification`, `friccion`, `commit_message`,
`commit_message_source` y `review_outcome` si existen en el metadata del run).
Los comentarios incluyen `author` y `body`. Los eventos incluyen `kind` y `payload`.

#### Scenario: Payload de run en timeline
WHEN un run tiene `outcome = "completed"`, `summary` de 800 chars y `metadata` que
incluye la clave `friccion`
THEN el item `run_end` contiene `summary` truncada a 500 chars y `metadata_excerpt`
con la clave `friccion`; las demás claves de `metadata` no viajan en la respuesta

#### Scenario: Run sin ended_at
WHEN un run está en estado `running` y `ended_at` es null
THEN la respuesta incluye el item `run_start` pero no emite item `run_end` para ese run

### Requirement: Deteccion de ruta de logs de worker
El servidor SHALL detectar el directorio de logs de worker en este orden: (1) variable
de entorno `KANBAN_LOGS_DIR` si está definida; (2) directorio `kanban/logs` relativo
al directorio padre de la ruta `kanban.db` detectada. Si el directorio no existe, el
endpoint `/api/tasks/{id}/worker-log` SHALL responder HTTP 404 en lugar de lanzar un
error no controlado.

#### Scenario: KANBAN_LOGS_DIR definida
WHEN la variable `KANBAN_LOGS_DIR` apunta a un directorio existente
THEN el servidor busca logs en ese directorio y no evalúa la ruta por defecto

#### Scenario: Ruta por defecto
WHEN `KANBAN_LOGS_DIR` no está definida y `KANBAN_DB` resuelve a
`C:\Users\jastorga\AppData\Local\hermes\kanban.db`
THEN el servidor busca logs en
`C:\Users\jastorga\AppData\Local\hermes\kanban\logs\`

### Requirement: Endpoint de log de worker
El servidor SHALL responder `GET /api/tasks/{id}/worker-log?tail=N` con
`{task_id, lines, truncated}` donde `lines` es un array con las últimas `tail`
líneas del archivo `{KANBAN_LOGS_DIR}/{task_id}.log`. El parámetro `tail` MUST ser
un entero entre 1 y 500 (por defecto 100); valores fuera de rango se recortan al
límite más cercano. Si el archivo no existe, MUST responder HTTP 404.

#### Scenario: Cola de log existente
WHEN la card `t_9df512af` tiene un archivo de log y se consulta
`/api/tasks/t_9df512af/worker-log?tail=20`
THEN la respuesta incluye hasta 20 líneas y `truncated` es `true` si el archivo
tiene más de 20 líneas

#### Scenario: Log inexistente
WHEN el archivo `{KANBAN_LOGS_DIR}/t_00000000.log` no existe y el id `t_00000000` es
formato hexadecimal válido pero no existe en la DB
THEN la respuesta es HTTP 404 con body `{"error": "not found"}`
