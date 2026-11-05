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
La UI SHALL usar un tema oscuro con variables CSS coherentes con el dashboard real de Hermes (`--color-bg`, `--color-surface`, `--color-text`, `--color-accent`, `--radius`) cuyos valores MUST tomarse del dashboard real de Hermes (pagina Kanban de `hermes dashboard`), no inventarse, y una tipografia monoespaciada para ids y modelos.

#### Scenario: Tema oscuro aplicado
WHEN la página carga
THEN el fondo de la página es oscuro, los textos son claros y los chips de estado son píldoras de color

#### Scenario: Variables CSS coherentes con dashboard real
WHEN el qa inspecciona el CSS del visor y compara con el dashboard real de Hermes (pagina Kanban)
THEN los valores de `--color-bg`, `--color-surface`, `--color-text`, `--color-accent` y `--radius` del visor son iguales a los del dashboard real, o se documenta la diferencia con justificacion en el reporte de QA
