# Proposal

## Why

Los conectores SVG del visor son casi invisibles (color `#5a7d78` → 3.91:1 sobre el fondo,
casi recto cuando cards están cerca) y la lista de grupos no tiene orden útil (sale en
inserción DB, el grupo activo puede estar al fondo). El usuario pide mejorar conectores,
orden izquierda y paleta de colores.

## What Changes

- **Conectores SVG**: aumentar tensión horizontal de la curva Bezier (mínimo 80 px de separación
  en los puntos de control), punta de flecha más grande (10×8 px), color `--color-arrow` con
  contraste ≥ 4.5:1 sobre `--color-bg`.
- **Paleta**: actualizar `--color-arrow` en `:root` (elección de Juan entre opción 1 ámbar y
  opción 2 verde-eléctrico); resto de la paleta base sin cambio.
- **Orden de grupos** (pendiente respuesta Q1): ordenar la lista izquierda por actividad
  reciente o creación reciente (requeriría campo nuevo en `/api/groups` → MODIFIED `visor-api`),
  o alfabético Z→A (solo frontend).
- **Color de conector por estado del padre** (pendiente respuesta Q3): si Juan lo aprueba,
  reutiliza las variables CSS de estado ya definidas, sin cambio de API.

## Capabilities

### New Capabilities

*(ninguna)*

### Modified Capabilities

- `visor-ui`: nueva requirement sobre calidad visual de conectores SVG (curva, marker, contraste)
  — lo que el conector debe parecer en pantalla, hoy no está especificado.
- `visor-api` (CONDICIONAL Q1): si el orden de grupos va por la API, nuevo campo
  `max_started_at` o `max_created_at` en la respuesta de `GET /api/groups`.

## Impact

- `index.html`: función `drawArrows` (L1158–1194), bloque `<defs>` del SVG (L799–803),
  variable `--color-arrow` en `:root` (L70).
- `server.py`: función `api_groups` (L136–169), solo si se elige ordenación vía API (Q1a/Q1b).
- Ninguna dependencia nueva. Ningún cambio de contrato de API si se elige Q1c (alfabético).
- Tests existentes (67) no prueban renderizado visual; requieren runner de browser (QA manual).
