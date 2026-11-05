## Capability: visor-api

## ADDED Requirements

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

---

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

---

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

---

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

---

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

---

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
