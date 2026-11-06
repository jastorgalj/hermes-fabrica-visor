## Capability: visor-ui

## ADDED Requirements

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

## MODIFIED Requirements

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
