## Capability: visor-api

## MODIFIED Requirements

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
