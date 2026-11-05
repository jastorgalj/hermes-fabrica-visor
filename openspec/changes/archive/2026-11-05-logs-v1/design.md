# Design

## Context

Ver `proposal.md` para la motivación. `server.py` Python 3.14 stdlib, DB solo lectura
(`file:...?mode=ro`). `index.html` JS vanilla sin dependencias.

## Goals / Non-Goals

**Goals:** Nuevos endpoints de timeline y worker-log en `server.py`. Sección de
timeline en el panel lateral de `index.html`. Validación de task_id (`^t_[0-9a-f]+$`)
exclusivamente en el endpoint `/api/tasks/{id}/worker-log` (el único que construye
una ruta de archivo).

**Non-Goals:** Transcripts de agentes (`profiles/*/state.db`). Autenticación. Cache
del lado del servidor. Auto-refresco del timeline.

## Decisions

**D1 — Un endpoint dedicado (`/timeline`) en lugar de ampliar `/api/tasks/{id}`.**
La respuesta de timeline puede superar fácilmente 50 KB (204 heartbeats × 100 B
cada uno); mezclarla en el endpoint existente rompería la carga rápida del panel de
estadísticas. Separar evita regresión y permite cargar bajo demanda.

**D2 — Mezcla cronológica por SQL UNION con columna `ts` normalizada.**
`task_runs` usa `started_at`/`ended_at`; `task_comments` y `task_events` usan
`created_at`. La mezcla se resuelve en Python con `heapq.merge` o una lista
ordenada; la query principal trae las filas separadas y Python las fusiona para
evitar un UNION genérico que dificultaría el test de tipos.

**D3 — `metadata_excerpt`: extraer solo 5 claves en el servidor.**
El metadata de un run puede pesar varios KB (incluye `git_log`, `commits`). Enviar
solo `verification`, `friccion`, `commit_message`, `commit_message_source` y
`review_outcome` limita el payload a < 500 B típicos.

**D4 — Logs de worker: solo lectura + validación de task_id contra DB.**
El path del log se construye `{KANBAN_LOGS_DIR}/{task_id}.log` donde `task_id`
pasa primero por regex `^t_[0-9a-f]+$` y luego se verifica que exista en la DB;
no se acepta ningún path externo → sin path traversal.

**D5 — No `innerHTML` en ningún punto del panel de timeline.**
Todo el contenido dinámico se inserta con `textContent` o se crean nodos con
`document.createElement`. Mismo patrón ya establecido en `index.html`.

## Risks / Trade-offs

[Riesgo payload grande] Tasks con 200+ heartbeats + limit=200 → `truncated=true`
el usuario no ve todos los eventos sin activar heartbeats. Mitigación: el contador
de heartbeats siempre visible informa cuántos se omiten.

[Riesgo orden no determinista] Dos items con el mismo `ts` provenientes de tablas
distintas no tienen un orden canónico en SQL. Mitigación: en Python, dentro del
mismo `ts` se ordena por `(ts, table_priority, row_id)` donde
`table_priority = {run_start: 0, event: 1, comment: 2, run_end: 3}`.

[Riesgo schema no versionado] Hermes puede añadir columnas a `task_events.payload`
o cambiar kinds sin aviso. Mitigación: el payload se transmite como string JSON
opaco; el frontend lo muestra como texto, no lo interpreta.

[Riesgo logs internos expuestos] Los logs de worker pueden contener rutas de
archivos locales. El endpoint es `127.0.0.1`-only y requiere que el task_id exista
en la DB; el usuario es el único que puede acceder. Decisión [JUAN] registrada en
propuesta.md P3.
