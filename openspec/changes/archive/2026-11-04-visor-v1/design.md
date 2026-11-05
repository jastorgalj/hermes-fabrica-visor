# Design: visor-v1

## Architecture

```
fabrica-visor/
├── server.py          # API HTTP + file server (Python 3.14 stdlib)
└── index.html         # SPA: todo el JS + CSS inline
```

La API y la UI están en archivos separados para permitir reemplazar la UI por un plugin del dashboard de Hermes sin cambiar el servidor.

## DB Path detection

```python
import os, pathlib, sys

def find_db() -> str:
    candidates = []
    if env := os.environ.get("KANBAN_DB"):
        candidates.append(("KANBAN_DB env", env))
    if localappdata := os.environ.get("LOCALAPPDATA"):
        candidates.append(("%LOCALAPPDATA%\\hermes\\kanban.db", f"{localappdata}\\hermes\\kanban.db"))
    candidates.append(("~/.hermes/kanban.db", str(pathlib.Path.home() / ".hermes" / "kanban.db")))
    for label, path in candidates:
        if pathlib.Path(path).exists():
            return path
    tried = "\n  ".join(f"{label} = {path}" for label, path in candidates)
    sys.exit(f"ERROR: kanban.db no encontrado. Rutas probadas:\n  {tried}\nDefine KANBAN_DB=<ruta_absoluta>")
```

Orden de búsqueda: (1) `KANBAN_DB` env si está definida; (2) `%LOCALAPPDATA%\hermes\kanban.db` (Windows); (3) `~/.hermes/kanban.db`; si ninguna existe → mensaje claro + exit sin traceback.

## Data model (kanban.db — solo lectura)

### Grouping criterion
El primer token del título hasta el primer espacio o dos puntos.
- `MTD-357 backend: ...` → key `MTD-357`
- `trail-solo-grafo 1/2:` → key `trail-solo-grafo`
- Título sin patrón → key `(sin-grupo)`

Implementación: `re.match(r'^([^\s:]+)', title)`.

### Key queries

**groups endpoint:**
```sql
SELECT id, title, assignee, status, block_kind, model_override, created_at, completed_at
FROM tasks
WHERE status != 'archived'
```
Agrupar en Python por regex.

**runs per task:**
```sql
SELECT id, task_id, outcome, started_at, ended_at, profile
FROM task_runs
WHERE task_id IN (...)
```

**changes_requested count per task:**
```sql
SELECT task_id, count(*) as cnt
FROM task_events
WHERE kind = 'changes_requested' AND task_id IN (...)
GROUP BY task_id
```

**links del subgrafo:**
```sql
SELECT parent_id, child_id FROM task_links
WHERE parent_id IN (...) AND child_id IN (...)
```

## WAL concurrency

SQLite WAL mode permite N lectores + 1 escritor concurrentes sin bloqueo. Abrir con `mode=ro` garantiza que el visor nunca entra en la cola de escritura. El dispatcher usa `BEGIN IMMEDIATE` para escrituras; los reads del visor no interfieren. Verificado: `PRAGMA journal_mode` retorna `wal` en la DB actual.

## Heartbeat filtering

`task_events` tiene 1326 heartbeats sobre 2035 eventos totales (65%). Las queries del visor NO leen heartbeats (filtran por kinds específicos o no leen events en bulk). La query de events recientes en el detalle de card tiene `LIMIT 50 ORDER BY id DESC` y puede filtrar `kind != 'heartbeat'` para evitar saturar el panel.

## Flow step mapping (Python dict)

```python
FLOW_STEP = {
    "explorer": "F0 Explorar",
    "coder":    "Implementar",
    "reviewer": "Review",
    "qa":       "QA",
    "closer":   "Cierre",
}
# Fallback: show raw assignee name
```

## Status color palette (CSS)

| Status | Color |
|--------|-------|
| todo | `#4b5563` (gris) |
| ready | `#1d4ed8` (azul) |
| running | `#065f46` (verde intenso) |
| review | `#92400e` (naranja oscuro) |
| blocked | `#7f1d1d` (rojo oscuro) |
| scheduled | `#4c1d95` (morado) |
| done | `#14532d` (verde tenue) |
| archived | `#1f2937` (gris oscuro) |

## DAG rendering

Algoritmo de niveles (topological sort):
1. Calcular in-degree de cada nodo dentro del grupo.
2. Nodos con in-degree 0 → nivel 0.
3. BFS: cada nodo hereda `max(nivel_padres) + 1`.
4. Renderizar como columnas de flexbox verticales, una por nivel.
5. Flechas SVG: calcular bounding boxes de los elementos y dibujar líneas `parent-right → child-left`.

Limitación: flechas SVG sobre un contenedor overflow-x:scroll requieren calcular posiciones absolutas con `getBoundingClientRect`. El coder debe usar `position: absolute` en el SVG overlay sobre el contenedor del grafo.

## Auto-refresh

```javascript
setInterval(async () => {
  await refreshGroups();          // siempre
  if (activeGroupKey) {
    await refreshGroup(activeGroupKey);  // solo si hay selección
  }
  updateTimestamp();
}, 10_000);
```

No se usa `location.reload()` ni manipulación de formularios.

## XSS prevention

Toda inserción en el DOM usa `element.textContent = data.title` (nunca `innerHTML = data.title`). Para construir HTML estructural, se usa `document.createElement` + `appendChild`. El servidor serializa JSON con `json.dumps()` que escapa automáticamente `<`, `>`, `&` en strings.

## Decisions

| # | Decisión | Razón |
|---|----------|-------|
| 1 | Polling cada 10 s en vez de SSE/WS | KISS; latencia de 10 s es aceptable para un visor de supervisión |
| 2 | No mostrar archivadas por defecto | Saturan la vista; el usuario puede pedir un toggle |
| 3 | CSS propio inline, sin CDN | Funciona sin internet; portable |
| 4 | DAG por niveles (no fuerza physics) | Suficiente para 5-20 nodos; sin librería |
| 5 | Heartbeats excluidos del panel de eventos | 65% del volumen son heartbeats; añadir ruido sin valor |
| 6 | Escape delegado al frontend (textContent) | El backend entrega datos en bruto; el frontend es quien inserta en el DOM |
