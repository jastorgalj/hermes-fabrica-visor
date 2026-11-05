# Tasks

## Grupo 1 — Backend: validación y endpoint de timeline

- [x] `server.py`: implementar `api_task_timeline(conn, task_id, limit, heartbeats)` que mezcla
      `task_runs` (run_start + run_end), `task_comments` y `task_events` en lista cronológica;
      ordena por `(ts, table_priority, row_id)` y aplica `limit`; calcula `heartbeat_count`
      y `truncated`; extrae `metadata_excerpt` con 5 claves fijas
      (cubre requirements «Endpoint de timeline de card», «Parametros de filtro de timeline»,
      «Formato de items en timeline de card»)
- [x] `server.py`: routing `GET /api/tasks/{id}/timeline` con 404 si la task no existe
- [x] **Test rojo** `tests/test_api.py`: verificar orden cronológico con datos sintéticos de
      las tres tablas; heartbeat_count correcto cuando `heartbeats=false`; `truncated=true` con
      limit pequeño; 404 con id `t_00000000` (hexadecimal válido, inexistente en DB);
      `metadata_excerpt` devuelve solo las 5 claves; `Run sin ended_at` → item run_end ausente

## Grupo 2 — Backend: logs de worker

- [x] `server.py`: implementar `find_logs_dir(db_path)` con detección de `KANBAN_LOGS_DIR` y
      fallback a `{dirname(db_path)}/kanban/logs`
- [x] `server.py`: implementar `api_task_worker_log(task_id, tail, logs_dir)` que lee las
      últimas `tail` líneas del archivo `{logs_dir}/{task_id}.log`; `tail` recortado a [1,500];
      404 si el archivo no existe
- [x] `server.py`: routing `GET /api/tasks/{id}/worker-log` con validación de task_id
- [x] **Test rojo** `tests/test_api.py`: 200 con cola correcta; `truncated=true` si el archivo
      tiene más líneas que `tail`; 404 cuando el archivo no existe; `tail` fuera de rango se
      recorta al límite (1 y 500); 400 con id inválido

## Grupo 3 — Frontend: sección de timeline en panel lateral

- [x] `index.html`: añadir sección «Línea de tiempo» al panel lateral (debajo de stats), con
      indicador de carga; disparar `fetchTimeline(task_id)` al hacer clic en la card por
      primera vez; NO disparar en el poll de 10 s; conservar scroll del panel entre polls
      (cubre requirements «Linea de tiempo de card», «Carga bajo demanda de timeline»)
- [x] `index.html`: renderizar items de timeline con icono/color por tipo usando solo variables
      CSS de `:root`; insertar todos los datos con `textContent`, nunca `innerHTML`
      (cubre requirements «Colores e iconos de items en timeline», «Linea de tiempo de card»)
- [x] `index.html`: toggle/checkbox «Mostrar heartbeats» + contador «N heartbeats» siempre
      visible; al activar, re-fetch con `heartbeats=true`
      (cubre requirement «Filtro de heartbeats en linea de tiempo»)
- [x] `index.html`: truncar comentarios > 300 chars con botón Expandir/Colapsar; comentarios
      ≤ 300 chars siempre completos
      (cubre requirement «Expandir y colapsar comentarios en timeline»)
- [x] `index.html`: sección acordeón «Log de worker» debajo del timeline; fetch bajo demanda
      a `/api/tasks/{id}/worker-log?tail=100`; si 404 mostrar «Sin log disponible»; usar
      `textContent` en bloque monoespaciado
      (cubre requirement «Seccion de log de worker en panel lateral»)

## Grupo 4 — Validación de cierre (suite completa)

Todos los tests se corren desde la raíz del worktree: `python -m unittest discover -s tests`

- [x] **E2E-TL-01** Abrir `http://127.0.0.1:8787`, clic en card `t_3275a989` →
      sección «Línea de tiempo» aparece; items ordenados cronológicamente;
      tipos `run_start`, `run_end`, `comment`, `event` con iconos distintos
- [x] **E2E-TL-02** Con la card abierta, esperar 10 s → el grafo se actualiza pero
      el contenido y posición de scroll de la sección de timeline no cambian
- [x] **E2E-TL-03** Verificar contador de heartbeats visible; activar toggle →
      heartbeats aparecen en la lista intercalados cronológicamente
      (aviso de truncado: FALLA-1 de QA corregida en t_111e2dda, verificada en browser por orquestador)
- [x] **E2E-TL-04** Comentario largo (> 300 chars) se muestra truncado con botón
      «Expandir»; al hacer clic se muestra completo y el botón dice «Colapsar»
- [x] **E2E-TL-05** Expandir acordeón «Log de worker» → aparecen líneas de log en
      bloque monoespaciado; para una card sin log, aparece «Sin log disponible»
- [x] **Unit-TL-01** `api_task_timeline`: orden cronológico con 3 items de tablas distintas
      con mismo `ts` → se ordena por `(ts, table_priority, row_id)`
- [x] **Unit-TL-02** `api_task_timeline`: heartbeat_count = 50 cuando hay 50 heartbeats,
      independientemente del parámetro `heartbeats`
- [x] **Unit-TL-03** `api_task_timeline`: `truncated=true` con `limit=2` y 3 items reales
- [x] **Unit-TL-04** `api_task_timeline`: `metadata_excerpt` devuelve exactamente las 5 claves
      previstas (ninguna extra) cuando el metadata del run las tiene todas
- [x] **Unit-TL-05** `api_task_timeline`: run con `ended_at=null` → no emite item `run_end`
- [x] **Unit-TL-06** `api_task_timeline`: `summary` de 800 chars → `metadata_excerpt.summary`
      truncado a 500 chars
- [x] **Unit-VAL-01** `GET /api/tasks/../../passwd/worker-log` → HTTP 400 `{"error": "invalid task_id"}`
- [x] **Unit-VAL-02** `GET /api/tasks/t_00000000/timeline` (id hexadecimal válido, no existe en DB) → HTTP 404
- [x] **Unit-LOG-01** `api_task_worker_log`: `tail=20` con archivo de 30 líneas →
      devuelve las 20 últimas y `truncated=true`
- [x] **Unit-LOG-02** `api_task_worker_log`: archivo inexistente → HTTP 404
- [x] **Unit-LOG-03** `api_task_worker_log`: `tail=0` → recortado a 1; `tail=600` → recortado
      a 500
- [x] **Unit-LOG-04** `find_logs_dir`: cuando `KANBAN_LOGS_DIR` está definida, se usa esa
      ruta y se ignora la por defecto
- [x] **Regresion-API** Correr `python -m unittest discover -s tests` → 0 fallos en tests
      existentes de `/api/groups`, `/api/group/{key}`, `/api/tasks/{id}`
