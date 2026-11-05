# Proposal: visor-v1 — Visor de solo lectura del flujo de la fábrica de agentes

## Summary

Visor web local de solo lectura que muestra en tiempo cuasi-real el estado de las cards del tablero kanban de Hermes, agrupadas por issue/proyecto, con el grafo de dependencias entre cards, estadísticas de iteraciones y marcado de gates humanos pendientes.

## Problem

El usuario no puede saber de un vistazo en qué paso está cada issue, cuántas iteraciones lleva, cuáles cards están esperando su decisión ni cuánto ha costado cada intento. La única superficie disponible es el dashboard integrado de Hermes, que no tiene vista de flujo por issue ni acumula el histórico de runs de forma compacta.

## Proposed solution

Una aplicación web mínima (`python3 server.py`) que:
1. Expone una API JSON leyendo `kanban.db` en modo solo lectura (WAL-safe, sin interferir con el dispatcher).
2. Sirve una SPA de un solo archivo HTML con JS vanilla y CSS propio (sin CDN, sin build step, sin npm).
3. Se auto-refresca cada 10 s via polling sin recargar la página.

La capa de datos (API) queda separada de la UI para permitir migrar la UI a plugin del dashboard de Hermes en el futuro.

## Scope

**Dentro del alcance (v1):**
- API de solo lectura sobre `kanban.db`: grupos, cards, runs, links, eventos
- UI: listado de grupos (issues), grafo DAG de cards por grupo, panel de detalle por card
- Estadísticas de iteración por card: runs totales, rondas de `changes_requested`, fallos (crashed/rate_limited/reclaimed/gave_up), duración total y por run
- Resaltado de cards `blocked` con `block_kind = 'needs_input'`
- Auto-refresco cada 10 s sin recarga de página
- Escape de todos los datos de la DB (XSS prevention)
- Ligado solo a `127.0.0.1`

**Fuera del alcance (v1):**
- Autenticación
- Escritura sobre el tablero (el visor es read-only)
- Vista de flujo tipo n8n (interactivo, drag-drop) — es el goal v2
- Plugin integrado del dashboard de Hermes — se mantiene como sistema separado
- Multi-board (solo el board `default` de `~/.hermes/kanban.db`)
- Notificaciones push o WebSocket (polling es suficiente)

## Stack (decisión pendiente de [JUAN])

| Opción | Runtime | Deps externas | Ventaja | Desventaja |
|--------|---------|--------------|---------|------------|
| **A — Python stdlib (Recomendada)** | python 3.14 | Ninguna | Cero dependencias extra; sqlite3 y http.server son stdlib | El routing HTTP manual es más verboso |
| **B — Bun + bun:sqlite** | bun | Ninguna (bun:sqlite es built-in) | Código más limpio, TypeScript, routing nativo | Requiere Bun instalado (ya disponible) |

**Recomendación A**: KISS absoluto. Python 3.14 ya está; `sqlite3` y `http.server` son stdlib. El visor nunca va a crecer tanto como para que la verbosidad de BaseHTTPRequestHandler sea un problema. Bun también es viable y algo más ergonómico, pero añade Bun como requisito runtime aunque ya esté instalado.

## Open questions

1. **[JUAN]** Stack: opción A (Python stdlib) o B (Bun)? Recomendada: A.
2. **[JUAN]** Criterio de agrupación: el primer token del título separado por espacio o dos puntos (p. ej. `MTD-357`, `trail-solo-grafo`, `fabrica-visor`). ¿Aceptas este criterio? Límite: títulos sin ese patrón quedan en grupo `(sin grupo)`.
3. **[JUAN]** Intervalo de refresco: 10 s (propuesto). ¿Ajustar?
4. **[JUAN]** ¿El visor debe mostrar cards archivadas? Por defecto las excluyo para no saturar la vista; se pueden incluir con un toggle.
5. **[JUAN]** Puerto: propongo `8787`. ¿Cambiar?
