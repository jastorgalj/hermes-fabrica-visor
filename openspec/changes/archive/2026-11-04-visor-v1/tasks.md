# Tasks: visor-v1

## Grupo 1 — API: servidor y endpoints

- [x] Crear `server.py` con `BaseHTTPRequestHandler` ligado a `127.0.0.1:8787` (configurable vía variable `PORT`).
  - Verificación: `python3 server.py &` arranca sin error; `curl http://127.0.0.1:8787/api/groups` responde JSON.
- [x] Implementar apertura de DB con `sqlite3.connect("file:<ruta>?mode=ro", uri=True)` usando la función `find_db()` del design (detecta en orden: `KANBAN_DB` env → `%LOCALAPPDATA%\hermes\kanban.db` → `~/.hermes/kanban.db`; si ninguna existe, sale con mensaje claro sin traceback).
  - Verificación: el proceso no puede ejecutar `INSERT INTO tasks` (lanza `sqlite3.OperationalError: attempt to write a readonly database`); arrancar sin `KANBAN_DB` en Windows encuentra la DB en `%LOCALAPPDATA%\hermes\kanban.db`.
- [x] Implementar `GET /api/groups`: query a `tasks` donde `status != 'archived'`; agrupar por regex `^([^\s:]+)`; retornar array `{key, label, task_count, running_count, blocked_input_count}`.
  - Verificación: con el board actual (37 tasks), la respuesta contiene al menos 6 grupos (`MTD-357`, `MTD-356`, `MTD-358`, `MTD-359`, `MTD-360`, `MTD-361`).
- [x] Implementar `GET /api/group/{key}`: retornar `{key, tasks: [...], links: [...]}`. Cada task incluye `run_count`, `changes_requested_count`, `failure_count`, `total_duration_seconds`, `runs`. Los links son solo los intra-grupo.
  - Verificación: `/api/group/MTD-360` retorna 7 tasks y sus links; `run_count` para t_d844dbb4 es >= 1.
- [x] Implementar `GET /api/tasks/{id}`: retornar task completa + `comments` + `events` (máximo 50, `kind != 'heartbeat'`, ordenados por `id DESC`). HTTP 404 si no existe.
  - Verificación: `/api/tasks/t_9df512af` retorna la card actual; `/api/tasks/t_noexiste` retorna 404.
- [x] Agregar cabeceras `Cache-Control: no-cache` y `Content-Type: application/json` en todas las respuestas de `/api/`.
  - Verificación: `curl -I http://127.0.0.1:8787/api/groups` muestra ambas cabeceras.

## Grupo 2 — UI: estructura base y tema

- [x] Crear `index.html` con la barra superior: título "Fábrica Hermes — Visor de flujo", timestamp de último refresco y dot de estado (OK/Error). Todo el CSS en `<style>` inline; no hay imports de red.
  - Verificación: la página carga con `python3 server.py` y todos los assets vienen del servidor local (no hay peticiones a dominios externos en DevTools > Network).
- [x] Implementar variables CSS tomando los valores reales del dashboard de Hermes: abrir `hermes dashboard` (página Kanban), inspeccionar las variables `--color-*` y `--radius` del DOM, y copiarlas en el `:root` de `index.html`. Tipografía monoespaciada para ids y modelos.
  - Verificación: el inspector de Chrome muestra las variables definidas en `:root` con los mismos valores que el dashboard de Hermes; cualquier diferencia está justificada en un comentario CSS.
- [x] Implementar lista de grupos en el sidebar izquierdo con conteos. Al hacer clic, el grupo queda seleccionado y se muestra su grafo en el área principal.
  - Verificación: hacer clic en "MTD-357" muestra el grafo de ese grupo sin recargar la página.

## Grupo 3 — UI: grafo DAG y panel de card

- [x] Implementar el renderizado DAG: calcular niveles topológicos (BFS sobre `links`), renderizar columnas de flexbox, una por nivel. Cards sin dependencias en nivel 0.
  - Verificación: el grupo `MTD-360` (7 cards con dependencias conocidas) muestra las cards en al menos 3 columnas con orden correcto (parent siempre a la izquierda del child).
- [x] Implementar las flechas SVG sobre el contenedor del grafo, calculando posiciones con `getBoundingClientRect`. El SVG es un overlay `position: absolute` sobre el contenedor.
  - Verificación: las flechas apuntan del borde derecho del parent al borde izquierdo del child en el grupo MTD-360.
- [x] Implementar colores de fondo por status en las cards (tabla del design.md). Implementar chip de modelo si `model_override != null`. Implementar chip de flow step desde assignee.
  - Verificación: una card con `status=running` tiene fondo `#065f46`; una con `model_override` muestra el chip naranja.
- [x] Implementar resaltado de `needs_input`: borde rojo `2px solid #ef4444` + icono ⚠ + texto "Espera decisión" para cards con `status=blocked` y `block_kind=needs_input`.
  - Verificación: la card t_9df512af (esta misma, cuando se bloquee con needs_input) muestra el resaltado.
- [x] Implementar panel lateral de estadísticas al hacer clic en una card: `fetch /api/tasks/{id}`, mostrar runs totales, changes_requested_count, failure_count, duración total y lista de runs individuales con outcome, perfil y duración en segundos.
  - Verificación: hacer clic en una card con múltiples runs muestra la lista correcta de outcomes.
- [x] Verificar XSS: todos los datos de texto se insertan via `textContent`, nunca `innerHTML` con datos de la API.
  - Verificación: ingresar manualmente en la DB un título con `<img src=x onerror=alert(1)>` y confirmar que la UI lo muestra como texto literal sin ejecutar el script.

## Grupo 4 — Validación de cierre (suite completa)

- [x] **[E2E-1]** Iniciar `python3 server.py`. Abrir `http://127.0.0.1:8787` en Chrome. La lista de grupos se muestra con al menos 6 issues. Seleccionar "MTD-360". El grafo aparece con 7 cards y flechas entre dependencias. Tiempo de carga de la vista < 2 s.
- [x] **[E2E-2]** Con el visor abierto en MTD-360, esperar 15 s. El timestamp del último refresco cambia sin recargar la página. El grupo seleccionado permanece activo.
- [x] **[E2E-3]** Hacer clic en cualquier card de MTD-360 que tenga runs. El panel lateral muestra `run_count >= 1`, `failure_count` correcto y la lista de runs con outcomes no vacía.
- [ ] **[E2E-4]** Detener `server.py`. El indicador de estado cambia a rojo "Error" en máximo 20 s.
- [x] **[E2E-5]** Con un título de test `<b>XSS</b>-test: prueba` en la DB (consulta SQL directa, solo para el test), el visor muestra la string literal en la card, sin formatear el elemento bold.
- [x] **[E2E-6]** Verificar que `netstat -an | grep 8787` no muestra `0.0.0.0:8787` (solo `127.0.0.1:8787`).
- [x] **[E2E-7]** Verificar que el proceso del servidor no puede escribir en la DB: intentar `UPDATE tasks SET title='x' WHERE id='t_xxx'` desde el mismo proceso Python lanza `OperationalError`.
- [x] **[E2E-8]** Con el board en vivo (dispatcher corriendo), dejar el visor abierto 2 min. No se producen errores en la consola del browser ni en el log del servidor. Las cards en `running` muestran el estado correcto.
- [x] **[E2E-9]** Abrir el dashboard real de Hermes (`hermes dashboard`, página Kanban) y el visor en dos tabs. Comparar visualmente el estilo y tomar capturas de ambos. El aspecto del visor es coherente con el dashboard (misma paleta oscura, mismas proporciones de chips). Registrar en el reporte de QA los valores reales de `--color-*` y `--radius` del dashboard y los del visor; si difieren, justificarlos.
