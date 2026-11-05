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
El servidor SHALL responder `GET /api/groups` con un array JSON de objetos `{key, label, task_count, running_count, blocked_input_count}` donde `key` es el primer token del titulo (separado por espacio o dos puntos), agrupando todas las tasks con `status != 'archived'`.

#### Scenario: Grupos presentes
WHEN el board tiene tasks con títulos `MTD-357 backend: ...` y `trail-solo-grafo 1/2: ...`
THEN `/api/groups` retorna al menos `[{key:"MTD-357",...},{key:"trail-solo-grafo",...}]` con `task_count >= 1` en cada uno

#### Scenario: Titulo sin patron
WHEN existe una task cuyo título no contiene espacio ni dos puntos
THEN esa task aparece en el grupo con key `(sin-grupo)`

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
