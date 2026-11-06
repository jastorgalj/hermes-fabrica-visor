# visor-ui Specification

## Purpose
SPA de un solo archivo HTML sin dependencias de red que visualiza el flujo de la fábrica de agentes Hermes, mostrando el grafo de cards por issue, estadísticas de iteración y gates humanos pendientes, con auto-refresco cada 10 s.

## Requirements

### Requirement: SPA autocontenida sin CDN
La UI SHALL ser un unico archivo `index.html` sin dependencias de red; todo el CSS y JS MUST estar inline o en archivos locales servidos por el mismo servidor.

#### Scenario: Carga sin conexión
WHEN la máquina no tiene acceso a internet y se abre `http://127.0.0.1:8787`
THEN la página carga completamente, el CSS se aplica y el JS funciona sin errores en consola sobre recursos externos fallidos

### Requirement: Barra superior con estado
La UI SHALL mostrar una barra superior con el titulo "Fabrica Hermes — Visor de flujo", el timestamp del ultimo refresco y un indicador de estado de la conexion a la API (OK / Error).

#### Scenario: Header visible
WHEN la página carga y la API responde
THEN el header muestra el título, la hora de último refresco en formato `HH:MM:SS` y el indicador verde "OK"

#### Scenario: Error de conexion
WHEN la API no responde (servidor caído)
THEN el indicador cambia a rojo "Error" y el timestamp deja de actualizarse

### Requirement: Lista de grupos seleccionable
La UI SHALL mostrar la lista de grupos (issues) con el numero de cards totales, en ejecucion y bloqueadas en espera de input humano, y permitir seleccionar un grupo para ver su grafo.

#### Scenario: Lista de grupos
WHEN el board tiene issues MTD-357 y trail-solo-grafo
THEN la lista muestra dos entradas con sus conteos, y al hacer clic en una se muestra su grafo

### Requirement: Grafo DAG con colores por estado
La UI SHALL renderizar el grafo de cards de un grupo como un DAG horizontal con niveles topologicos (nivel 0 = raices, nivel N = cards cuyos padres estan todos en niveles anteriores), arrows SVG entre cards dependientes, y color de fondo segun el estado de cada card.

#### Scenario: Colores por estado
WHEN se muestran cards con estados `todo`, `ready`, `running`, `review`, `blocked`, `scheduled`, `done`, `archived`
THEN cada estado tiene un color de fondo distinto según la tabla: todo=gris, ready=azul, running=verde intenso, review=naranja, blocked=rojo, scheduled=morado, done=verde tenue, archived=gris oscuro

#### Scenario: Arrows de dependencia
WHEN la card A es padre de la card B
THEN se muestra una línea SVG desde el borde derecho de A hasta el borde izquierdo de B

#### Scenario: Grafo sin dependencias
WHEN un grupo tiene cards sin ningún link entre ellas
THEN las cards se muestran en columna vertical en el nivel 0 sin flechas

### Requirement: Contenido de cada card en el grafo
Cada card en el grafo SHALL mostrar: titulo (truncado a 60 chars), perfil asignado, paso del flujo deducido del perfil (explorer=F0, coder=Implementar, reviewer=Review, qa=QA, closer=Cierre, otros=perfil literal), estado, y chip de modelo si `model_override` no es nulo.

#### Scenario: Card con model override
WHEN la card tiene `model_override = "claude-opus-4"` 
THEN la card muestra un chip naranja con el nombre del modelo

#### Scenario: Paso del flujo
WHEN la card tiene `assignee = "coder"` y `status = "running"`
THEN la card muestra "Implementar" como paso del flujo

### Requirement: Resaltado de needs_input
La UI SHALL resaltar visualmente con borde rojo y un icono alerta las cards con `status = "blocked"` y `block_kind = "needs_input"`, indicando que requieren decision del usuario.

#### Scenario: Card needs_input
WHEN una card tiene status=blocked y block_kind=needs_input
THEN la card tiene borde rojo, icono ⚠ y el texto "Espera decisión" visible sin hacer clic

### Requirement: Panel lateral de estadisticas de iteracion
Al hacer clic en una card, la UI SHALL mostrar un panel lateral con las estadisticas de iteracion: total de runs, rondas de `changes_requested`, fallos (crashes + rate_limited + reclaimed + gave_up), duracion total en minutos y la lista de runs con outcome, perfil y duracion individual.

#### Scenario: Panel de estadisticas
WHEN el usuario hace clic en una card que tuvo 3 runs (2 completados, 1 crashed)
THEN el panel muestra: "3 runs", "1 fallo", "0 rondas de cambios solicitados", y lista los 3 runs con sus outcomes

### Requirement: Auto-refresco sin recarga de pagina
La UI SHALL ejecutar un poll a `GET /api/groups` cada 10 s y, si el grupo activo esta seleccionado, tambien a `GET /api/group/{key}`, actualizando el DOM sin recargar la pagina ni perder la seleccion del usuario.

#### Scenario: Auto-refresco mantiene seleccion
WHEN el usuario tiene seleccionado el grupo "MTD-357" y pasan 10 s
THEN el grafo se actualiza con datos frescos y la selección "MTD-357" permanece activa

#### Scenario: Estado cambia entre polls
WHEN una card pasa de running a done entre dos polls
THEN al siguiente poll el color de la card cambia de verde intenso a verde tenue sin acción del usuario

### Requirement: Insercion segura de datos en el DOM
La UI SHALL insertar todos los datos de texto de la API en el DOM usando `textContent` o equivalente seguro, nunca mediante `innerHTML` con datos no sanitizados, para prevenir inyeccion HTML.

#### Scenario: Titulo con HTML
WHEN el título de una card contiene `<b>bold</b>`
THEN el DOM muestra la string literal `<b>bold</b>` como texto, no el elemento bold renderizado

### Requirement: Tema oscuro coherente con Hermes
La UI SHALL usar un tema oscuro con variables CSS en `:root` (`--color-bg`,
`--color-surface`, `--color-text`, `--color-accent`, `--radius`) cuyos valores MUST
tomarse de la ventana de Hermes desktop (perfil `nous`, oscuro), no del dashboard web
ni inventarse, y una tipografia monoespaciada para ids y modelos. Valores medidos:
`--color-bg: #0d1015`, `--color-surface: #191b1f`, `--color-text: #e6edf3`,
`--color-accent: #4c89ff`; `--radius` no cambia.

#### Scenario: Tema oscuro aplicado
WHEN la pagina carga
THEN el fondo es oscuro (#0d1015), los textos son claros (#e6edf3), el acento es
azul (#4c89ff), los chips de estado son pildoras de color y ningun fondo ni
superficie (sidebar, header, panel lateral, cards) tiene tono teal o verde de marca

#### Scenario: Variables CSS coherentes con dashboard real
WHEN el QA mide los colores de la ventana de Hermes desktop en ejecucion (captura
y muestreo de pixeles) y los compara con `--color-bg`, `--color-surface`,
`--color-text` y `--color-accent` del visor
THEN coinciden con diferencia por canal <= 4, o se documenta la diferencia con
justificacion en el reporte de QA

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

### Requirement: Conectores SVG con punta y trazo legibles
Los conectores SHALL ser una curva Bezier cubica con controles en `midX = (srcX + dstX) / 2`
y `stroke-width` de 2.5 px. El marker MUST ser `markerWidth="10"` `markerHeight="8"`,
poligono `points="0 0, 10 4, 0 8"`. Con 2 o mas conectores entrantes en una card, cada
punto de llegada MUST separarse 10 px del siguiente, centrados en la card.

#### Scenario: Cards con distinta altura
WHEN la card A y la card B tienen centros verticales distintos
THEN el conector muestra una curva en S, no una recta, y la punta de flecha mide
10x8 en el elemento marker

#### Scenario: Cards en la misma fila
WHEN la card A y la card B tienen el mismo centro vertical
THEN el conector es una recta horizontal con punta de flecha visible (resultado
aceptado, no es un defecto)

#### Scenario: Cuatro conectores convergen en una card
WHEN el QA abre el grupo MTD-360 y la card `t_8ab670cd` recibe 4 conectores
THEN las 4 puntas de flecha se distinguen una de otra, con 10 px entre puntos de
llegada consecutivos

### Requirement: Color de conectores SVG legible sobre fondo
El trazo del conector SHALL leer su color de `var(--color-arrow)` en `:root`;
MUST tener contraste >= 4.5:1 sobre `var(--color-bg)`. Ningún literal de color
(#hex, rgb, hsl) SHALL aparecer en el JS de conectores ni en atributos SVG inline
fuera de `:root`.

#### Scenario: Contraste de arrow sobre fondo
WHEN el QA calcula el contraste de --color-arrow sobre --color-bg
THEN el ratio es >= 4.5:1 según WCAG 2.1

#### Scenario: Sin literales de color en JS de conectores
WHEN el QA inspecciona la función drawArrows y el bloque defs del SVG
THEN no existe ningún literal de color fuera de la sección :root del CSS

### Requirement: Color de conector por estado del task padre
El trazo del conector SHALL usar `var(--color-arrow-done)`, `var(--color-arrow-running)`
o `var(--color-arrow-blocked)` según el status del task padre; para estados no mapeados
MUST usar `var(--color-arrow)`. El status MUST obtenerse del campo `status` en
`groupData.tasks` sin llamada adicional a la API.

#### Scenario: Color de conector por estado del padre
WHEN el QA abre el grupo MTD-360 en el browser y hay tasks con status done y running
THEN el conector cuyo padre es done usa --color-arrow-done (verde) y el de running usa
--color-arrow-running (azul), ambos visualmente distintos de --color-arrow (gris neutro),
sin que el frontend haya realizado ninguna llamada adicional a la API más allá de
/api/group/{key}

### Requirement: Contraste de variables de trazo de conectores
Las variables `--color-arrow-done`, `--color-arrow-running`, `--color-arrow-blocked` y
`--color-arrow` SHALL tener cada una contraste >= 4.5:1 sobre `var(--color-bg)`. Cada
variable MUST ser distinguible por hue de las demás. Las variables `var(--color-status-*)`
SHALL NOT usarse como trazo de conectores porque son rellenos de card con contraste
insuficiente (< 2:1) sobre el fondo para trazos finos.

#### Scenario: Contraste de variables de trazo calculado
WHEN el QA calcula el contraste de --color-arrow-done, --color-arrow-running,
--color-arrow-blocked y --color-arrow sobre --color-bg con la herramienta contrast_check.py
THEN todos los ratios son >= 4.5:1 y cada color tiene un hue visualmente distinto
(verde / azul / naranja / gris)

### Requirement: Orden de grupos en la lista izquierda por actividad reciente
La lista de grupos en el panel izquierdo SHALL ordenarse por el campo `last_activity`
que provee `/api/groups`, de mayor a menor (más reciente primero). Los grupos con
`last_activity = null` MUST aparecer al final. El orden MUST aplicarse en cada carga
inicial y en cada refresco periódico de la lista, sin requerir interacción del usuario.

#### Scenario: Grupo activo sube al tope
WHEN el board tiene al menos dos grupos y el grupo fabrica-visor tiene el
last_activity más reciente
THEN fabrica-visor aparece primero en la lista izquierda del visor

#### Scenario: Grupos sin actividad al final
WHEN existe un grupo cuyas tasks tienen started_at = null
THEN ese grupo aparece después de todos los grupos con last_activity no nula

### Requirement: Variables derivadas del tema recalculadas
Toda variable de `:root` derivada de la paleta teal anterior (`--color-surface-2`,
`--color-sidebar-bg`, `--color-sidebar-hover`, `--color-sidebar-active`,
`--color-header-bg`, `--color-panel-bg`, `--color-text-muted`, `--color-text-dim`,
`--color-border`, `--color-border-2`, `--color-chip-flow-bg`, `--color-chip-flow-text`)
SHALL recalcularse desde los valores medidos de Hermes desktop. Los colores semanticos
de estado (running, done, blocked, ok, error) se conservan.

#### Scenario: Sin teal residual
WHEN se busca en `index.html` los hex `#0a2828 #103634 #061f1f #0e2f2d #14453f #0f4c46 #9ff0e0`
THEN ninguno aparece, y el QA no ve tono teal en sidebar, header ni paneles
