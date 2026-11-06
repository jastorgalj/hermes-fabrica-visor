# Tasks

## Grupo 1: Mejora de conectores SVG

- [x] **T1 — Preparar baseline**: verificar `python -m unittest discover -s tests` → 67 tests OK
  antes de tocar `index.html`. Registrar resultado.

- [x] **T2 — Conectores: trazo, llegada separada y curva** (`index.html`, `drawArrows`, ~L1165-1195):
  Mantener `midX = (srcX + dstX) / 2` como punto de control (NO una tension minima fija:
  el espacio entre columnas es 48 px por `#graph-container { gap: 3rem }`, y 80 px cruzaria
  los controles). Subir `stroke-width` de 2 a 2.5. Para una card con n >= 2 conectores
  entrantes, desplazar el `dstY` de cada uno en pasos de 10 px, centrados en el centro de
  la card (orden estable: por `link.parent_id`). Con los extremos a la misma altura la curva
  ES una recta: aceptado, no lo "arregles". Criterio: en MTD-360 las 4 puntas que llegan a
  `t_8ab670cd` se ven separadas. Verifica por geometria (calcula los `d` de un caso con
  numeros), no solo a ojo; la QA lo confirma en browser.

- [x] **T3 — Punta de flecha mas grande** (`index.html`, bloque `<defs>` del SVG, ~L800-803):
  Cambiar `markerWidth="8" markerHeight="6" ... points="0 0, 8 3, 0 6"` a
  `markerWidth="10" markerHeight="8" refX="10" refY="4" ... points="0 0, 10 4, 0 8"`.

- [x] **T4 — Paleta Hermes desktop: actualizar `:root`** (`index.html`, bloque `:root`):
  Reemplazar los valores de la paleta vieja (fondo `#041c1c`, texto `#ffe6cb`, accent `#34d399`)
  por los medidos en la ventana de Hermes desktop (perfil `nous`, oscuro):
  - `--color-bg: #0d1015`
  - `--color-surface: #191b1f`
  - `--color-text: #e6edf3`
  - `--color-accent: #4c89ff` (MODIFICA el valor existente; no agregar variable duplicada)
  - `--color-arrow: #94a3b8` (contraste 7.43:1 sobre #0d1015)
  Recalcular TODAS las variables derivadas de la paleta teal anterior, en `:root`, desde los
  valores medidos de Hermes desktop (fondo `#0d1015`, sidebar `#191b1f`, item activo
  `#272d3a`, superficie azulada `#0f1621`, borde de foco `#263e70`): `--color-surface-2`,
  `--color-sidebar-bg`, `--color-sidebar-hover`, `--color-sidebar-active`,
  `--color-header-bg`, `--color-panel-bg`, `--color-text-muted`, `--color-text-dim`,
  `--color-border`, `--color-border-2`, `--color-chip-flow-bg/-text` (hoy teal verdoso
  `#0f4c46`/`#9ff0e0`: pasar a azul). Cada derivado con su contraste calculado (texto >= 4.5:1).
  Despues del cambio, `#0a2828 #103634 #061f1f #0e2f2d #14453f #0f4c46 #9ff0e0` no deben
  aparecer en `index.html` (grep por esos hex).
  Agregar las variables de trazo por estado (NUEVAS, no existían):
  - `--color-arrow-done: #4ade80` (contraste 10.94:1 sobre #0d1015)
  - `--color-arrow-running: #38bdf8` (contraste 8.89:1 sobre #0d1015)
  - `--color-arrow-blocked: #fb923c` (contraste 8.42:1 sobre #0d1015)
  Criterio: `contrast_check.py` reporta >= 4.5:1 para todos. Sin verdes de marca en
  fondos ni superficies (los colores semánticos de arrow sí pueden ser verdes porque
  son información de estado). Decisión Juan 2026-11-06 (card t_268fde83).

- [x] **T5 — Color de conector por estado del padre** (`index.html`, función `drawArrows`):
  En `drawArrows`, obtener `taskStatus` desde `groupData.tasks` por `link.parent_id`.
  Mapeo de colores (usar variables de trazo, NO var(--color-status-*)):
  - `done` → `var(--color-arrow-done)`
  - `running` → `var(--color-arrow-running)`
  - `blocked` → `var(--color-arrow-blocked)`
  - resto → `var(--color-arrow)`
  Sin llamada adicional a la API (el campo `status` ya viaja en `groupData.tasks`).
  Sin literales de color en JS. Decisión Juan 2026-11-06 (card t_268fde83).

- [x] **T6 — QA en browser (conectores + paleta + color por estado)**:
  Levantar el visor DESDE EL WORKTREE con `PORT=8794 python server.py` (el 8787 es el visor del usuario y sirve `main`, o sea el codigo viejo: probar ahi daria un falso resultado) y abrir `http://127.0.0.1:8794`; seleccionar grupo MTD-360 (7 cards, 6 conectores).
  Verificar (tabla comparativa con ventana de Hermes desktop en ejecución):
  | Variable | Valor visor | Valor Hermes desktop | Match |
  |---|---|---|---|
  | --color-bg | (leer del visor) | (MEDIR en la captura de la ventana Hermes.exe) | (calcular) |
  | --color-surface | (leer) | (medir) | (calcular) |
  | --color-text | (leer) | (medir) | (calcular) |
  | --color-accent | (leer) | (medir) | (calcular) |
  | Verdes de marca en fondos/superficies | (buscar en capturas y en `:root`) | — | (calcular) |
  Los valores esperados NO se copian de este archivo: se miden en la corrida. Un ✓ sin medicion es un espejo del spec.
  Verificar también:
  - Conectores entre cards de distinta altura: curva en S; entre cards de la misma fila: recta con punta visible (aceptado).
  - Las 4 puntas que llegan a t_8ab670cd se distinguen.
  - Sidebar, header y paneles sin tono teal/verde de marca (comparar con captura de Hermes desktop).
  - Punta de flecha proporcional al extremo de cada conector.
  - Color de flecha claramente visible sobre el fondo oscuro (slate #94a3b8 en estado neutro).
  - Conector cuyo padre es `done` tiene color distinto al de un padre `running`.
  - No hay literales de color en JS (inspección DevTools → Sources → index.html).
  Captura obligatoria antes/después como evidencia de QA.

## Grupo 2: Orden de grupos por actividad reciente

Decisión Juan 2026-11-06: opción a) max started_at DESC, campo nuevo en /api/groups.

- [x] **T7 — Agregar `last_activity` y orden DESC a `api_groups`** (`server.py`, L136–169):
  En la función `api_groups`, al construir el dict de cada grupo, calcular
  `last_activity = max(t['started_at'] for t in group_tasks if t.get('started_at')) or None`.
  Luego ordenar `list(groups.values())` por `g['last_activity'] or 0` DESC antes de retornar.
  El campo `last_activity` va en cada objeto del array JSON.
  Criterio: test unitario del endpoint `/api/groups` verifica que el grupo con
  started_at más reciente aparece primero y que last_activity está presente.

- [x] **T8 — Verificar que `renderGroups` respeta el orden del array** (`index.html`, `renderGroups`):
  El frontend DEBE usar el orden del array que devuelve `/api/groups` sin re-ordenar.
  Verificar que `renderGroups` no impone un orden propio (debe iterar el array tal cual).
  Criterio: grupo fabrica-visor aparece al tope en el browser cuando tiene el
  last_activity más reciente.

- [x] **T9 — QA en browser (orden de grupos)**:
  Con el visor del worktree en 8794, verificar que la lista izquierda muestra el grupo activo al tope.
  Captura antes/después.

## Validación final

- [x] **T10** — `python -m unittest discover -s tests` → 67 OK (mismo número, mismo resultado).
  Los tests no validan renderizado visual; los escenarios de QA en browser son la cobertura
  de los nuevos requirements.

- [x] **T11** — `openspec validate ux-v2 --strict` → 0 errores, 0 warnings.
