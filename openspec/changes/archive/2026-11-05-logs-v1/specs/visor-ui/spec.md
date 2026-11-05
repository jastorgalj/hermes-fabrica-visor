## Capability: visor-ui

## ADDED Requirements

### Requirement: Linea de tiempo de card
Cuando el panel lateral de la card esté visible, SHALL mostrar una sección de línea
de tiempo con todos los eventos, runs y comentarios mezclados en orden cronológico
ascendente. Cada item MUST mostrar el perfil asociado cuando esté disponible y la
hora formateada (`HH:MM:SS dd/mm`). Todos los datos de texto provenientes de la API
MUST insertarse en el DOM con `textContent`, nunca con `innerHTML`.

#### Scenario: Items de timeline en orden cronologico
WHEN la card `t_3275a989` tiene 6 runs, 4 comentarios y eventos variados
THEN la sección de timeline muestra todos los items ordenados por hora ascendente

#### Scenario: Perfil mostrado en cada item de run
WHEN un run_start tiene `profile = "coder"`
THEN el item muestra "coder" como texto en la línea de tiempo

#### Scenario: Insercion segura en timeline
WHEN el `body` de un comentario contiene `<script>alert(1)</script>`
THEN el DOM muestra la cadena literal como texto, sin ejecutar el script

---

### Requirement: Colores e iconos de items en timeline
Cada item SHALL mostrar un icono y color de fondo distintos según su tipo, usando
solo variables CSS de `:root`: `run_start` ▶ (var color running), `run_end` ■
(var color done si outcome=completed; var color blocked si crashed/gave_up/
rate_limited/reclaimed; gris en otro caso), `comment` 💬 (var color accent),
`event` 📌 (var color surface). Ningún color literal SHALL aparecer fuera de `:root`.

#### Scenario: Colores por tipo de item
WHEN la timeline muestra un run_end con outcome "completed" y un run_end con
outcome "crashed"
THEN el primero usa el color de done y el segundo el color de blocked, ambos
tomados de variables CSS de `:root`, no de valores literales

#### Scenario: Colores de variables CSS
WHEN el QA inspecciona el CSS de la sección de timeline
THEN no existe ningún valor de color literal (hex, rgb, hsl) fuera de la sección
`:root` del archivo

---

### Requirement: Filtro de heartbeats en linea de tiempo
La sección de timeline SHALL mostrar un contador de heartbeats siempre visible
(`N heartbeats`) y un control toggle/checkbox para incluirlos en la lista. Los
heartbeats MUST estar ocultos por defecto; al activar el toggle, la UI MUST
recargar el timeline con `heartbeats=true` en la query.

#### Scenario: Heartbeats ocultos por defecto con contador
WHEN se abre el panel de timeline de una card con 50 heartbeats
THEN la lista de items no muestra heartbeats y el contador indica "50 heartbeats"

#### Scenario: Toggle activa heartbeats
WHEN el usuario activa el toggle "Mostrar heartbeats"
THEN la UI realiza una nueva petición a `/api/tasks/{id}/timeline?heartbeats=true` y
los heartbeats aparecen intercalados en la lista cronológica

---

### Requirement: Expandir y colapsar comentarios en timeline
Los items de tipo `comment` con `body` de más de 300 caracteres SHALL mostrarse
truncados con un botón "Expandir"; al hacer clic, el body completo MUST quedar
visible y el botón cambiar a "Colapsar". Los comentarios de 300 chars o menos
MUST mostrarse siempre completos sin botón.

#### Scenario: Comentario largo truncado con boton expandir
WHEN un comentario tiene 2000 chars
THEN el item muestra los primeros 300 chars seguidos de "…" y un botón "Expandir"
visible; al hacer clic se muestra el texto completo y el botón dice "Colapsar"

#### Scenario: Comentario corto siempre completo
WHEN un comentario tiene 150 chars
THEN el item muestra el texto completo sin botón ni truncado

---

### Requirement: Carga bajo demanda de timeline
La sección de timeline SHALL cargarse solo cuando el usuario abre el panel lateral
de la card por primera vez, mediante una petición a
`GET /api/tasks/{id}/timeline?limit=200`. El auto-refresco de 10 s MUST NOT
volver a solicitar el timeline ni modificar el contenido de la sección una vez
cargada; el scroll del panel MUST conservarse entre polls.

#### Scenario: Timeline no se refresca en poll periodico
WHEN el usuario tiene abierto el panel de la card `t_3275a989` y pasan 10 s
THEN el poll actualiza el grafo y el panel de estadísticas pero la sección de
timeline mantiene su contenido y posición de scroll sin nueva petición HTTP

#### Scenario: Timeline carga al abrir el panel
WHEN el usuario hace clic en una card por primera vez
THEN la UI muestra un indicador de carga y realiza exactamente una petición a
`/api/tasks/{id}/timeline`; al recibirla, renderiza los items sin recargar la
página

---

### Requirement: Seccion de log de worker en panel lateral
Cuando el endpoint `/api/tasks/{id}/worker-log` esté disponible, el panel lateral
SHALL mostrar una sección acordeón "Log de worker" con las últimas 100 líneas del
log, expandible bajo demanda. Si el endpoint devuelve HTTP 404, la sección SHALL
mostrarse deshabilitada con el texto "Sin log disponible". Todos los datos de texto
MUST insertarse con `textContent`.

#### Scenario: Log disponible en acordeon
WHEN la card tiene un archivo de log y el usuario expande la sección "Log de worker"
THEN la UI realiza una petición a `/api/tasks/{id}/worker-log?tail=100` y muestra
las líneas en un bloque monoespaciado usando `textContent`

#### Scenario: Log no disponible
WHEN el endpoint devuelve HTTP 404
THEN la sección muestra "Sin log disponible" y no emite más peticiones
