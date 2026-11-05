# Proposal

## Why

El visor v1 muestra el grafo de cards pero no hay forma de ver qué ocurrió dentro de
cada card. Se quiere una línea de tiempo cronológica por card que mezcle runs,
comentarios y eventos leídos de `kanban.db`, para diagnosticar fallos y entender el
historial sin abrir logs externos.

## What Changes

- **API**: nuevo endpoint `GET /api/tasks/{id}/timeline` que devuelve una lista
  cronológica de items (run_start, run_end, comment, event) con heartbeat_count y
  límite configurable.
- **API**: nuevo endpoint `GET /api/tasks/{id}/worker-log?tail=N` que devuelve las
  últimas N líneas del log de worker de la card (`KANBAN_LOGS_DIR/{id}.log`).
- **API**: validación explícita del formato `^t_[0-9a-f]+$` en los endpoints de task
  individual, devolviendo HTTP 400 si no coincide (previene path traversal).
- **UI**: sección de línea de tiempo en el panel lateral de la card, cargada bajo
  demanda (no en el poll de 10 s), con icono/color por tipo de item.
- **UI**: toggle para mostrar/ocultar heartbeats con contador siempre visible.
- **UI**: expandir/colapsar comentarios largos (> 300 chars).

## Capabilities

### New Capabilities

*(ninguna: la feature extiende capacidades existentes)*

### Modified Capabilities

- `visor-api`: nuevos endpoints `/timeline` y `/worker-log`; validación de task_id.
- `visor-ui`: sección de línea de tiempo en el panel lateral de la card.

## Impact

- `server.py`: 2 funciones nuevas (`api_task_timeline`, `api_task_worker_log`) y
  validación de task_id; routing en `do_GET`; sin dependencias externas.
- `index.html`: sección de timeline en el panel lateral; JS de carga bajo demanda,
  toggle de heartbeats y expand/collapse de comentarios.
- `kanban.db` (solo lectura): queries sobre `task_runs`, `task_comments`, `task_events`.
- Nueva variable de entorno: `KANBAN_LOGS_DIR` (default: `{dirname(KANBAN_DB)}/kanban/logs`).
