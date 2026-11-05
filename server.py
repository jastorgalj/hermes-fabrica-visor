"""
server.py — Visor de flujo de la fábrica de agentes Hermes.
API HTTP de solo lectura + file server para index.html.
Sin dependencias externas: Python 3.14 stdlib únicamente.
"""
import os
import re
import sys
import json
import pathlib
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

FAILURE_OUTCOMES = frozenset({'crashed', 'rate_limited', 'reclaimed', 'gave_up'})

OPTIONAL_COLS = frozenset({'block_kind', 'model_override', 'provider_override'})

REQUIRED_TASK_COLS = (
    'id', 'title', 'assignee', 'status', 'created_at', 'completed_at'
)

# ---------------------------------------------------------------------------
# Detección de ruta de DB
# ---------------------------------------------------------------------------

def find_db() -> str:
    """Detecta la ruta de kanban.db en orden de prioridad.
    Si ninguna existe, imprime mensaje claro y sale sin traceback.
    """
    candidates = []
    if env := os.environ.get('KANBAN_DB'):
        candidates.append(('KANBAN_DB env', env))
    if localappdata := os.environ.get('LOCALAPPDATA'):
        candidates.append((
            '%LOCALAPPDATA%\\hermes\\kanban.db',
            os.path.join(localappdata, 'hermes', 'kanban.db'),
        ))
    candidates.append((
        '~/.hermes/kanban.db',
        str(pathlib.Path.home() / '.hermes' / 'kanban.db'),
    ))
    for label, path in candidates:
        if pathlib.Path(path).exists():
            return path
    tried = '\n  '.join(f'{label} = {path}' for label, path in candidates)
    sys.exit(
        f'ERROR: kanban.db no encontrado. Rutas probadas:\n  {tried}\n'
        f'Define KANBAN_DB=<ruta_absoluta>'
    )


# ---------------------------------------------------------------------------
# Apertura de DB (solo lectura)
# ---------------------------------------------------------------------------

def open_db(path: str) -> sqlite3.Connection:
    """Abre la DB en modo solo lectura con URI SQLite.
    Cualquier INSERT/UPDATE/DELETE lanzará sqlite3.OperationalError.
    """
    # Convertir backslashes a forward slashes para URI SQLite
    uri_path = str(pathlib.Path(path)).replace('\\', '/')
    uri = f'file:{uri_path}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_task_cols(conn: sqlite3.Connection) -> set:
    """Retorna el conjunto de nombres de columnas de la tabla tasks.
    Se consulta una vez al abrir para detectar columnas opcionales.
    """
    cur = conn.execute('PRAGMA table_info(tasks)')
    return {row['name'] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Lógica de agrupación
# ---------------------------------------------------------------------------

def _group_key(title: str) -> str:
    """Extrae el key de agrupación del título.
    Primer token hasta el primer espacio o dos puntos.
    Si el título está vacío o no hace match → '(sin-grupo)'.
    """
    if not title:
        return '(sin-grupo)'
    m = re.match(r'^([^\s:]+)', title)
    return m.group(1) if m else '(sin-grupo)'


# ---------------------------------------------------------------------------
# Endpoints de la API
# ---------------------------------------------------------------------------

def api_groups(conn: sqlite3.Connection, known_cols: set) -> list:
    """GET /api/groups — Array de grupos con conteos."""
    # Columnas a seleccionar (solo las que existen)
    extra = [c for c in OPTIONAL_COLS if c in known_cols]
    col_list = ', '.join(list(REQUIRED_TASK_COLS) + extra)

    cur = conn.execute(
        f"SELECT {col_list} FROM tasks WHERE status != 'archived'"
    )
    rows = cur.fetchall()

    groups: dict[str, dict] = {}
    for row in rows:
        task = dict(row)
        key = _group_key(task.get('title') or '')
        if key not in groups:
            groups[key] = {
                'key': key,
                'label': key,
                'task_count': 0,
                'running_count': 0,
                'blocked_input_count': 0,
            }
        g = groups[key]
        g['task_count'] += 1
        if task.get('status') == 'running':
            g['running_count'] += 1
        if (
            task.get('status') == 'blocked'
            and task.get('block_kind') == 'needs_input'
        ):
            g['blocked_input_count'] += 1

    return list(groups.values())


def api_group(
    conn: sqlite3.Connection, known_cols: set, key: str
) -> dict | None:
    """GET /api/group/{key} — Grafo del grupo con tasks y links."""
    extra = [c for c in OPTIONAL_COLS if c in known_cols]
    col_list = ', '.join(list(REQUIRED_TASK_COLS) + extra)

    # Obtener TODAS las tasks del grupo (incluidas archived, para el toggle UI)
    cur = conn.execute(f'SELECT {col_list} FROM tasks')
    all_tasks = [dict(row) for row in cur.fetchall()]

    group_tasks = [
        t for t in all_tasks if _group_key(t.get('title') or '') == key
    ]
    if not group_tasks:
        return None

    task_ids = [t['id'] for t in group_tasks]
    placeholders = ','.join('?' * len(task_ids))

    # Runs de las tasks del grupo
    cur = conn.execute(
        f'SELECT id, task_id, outcome, started_at, ended_at, profile '
        f'FROM task_runs WHERE task_id IN ({placeholders})',
        task_ids,
    )
    runs_by_task: dict[str, list] = {}
    for run in cur.fetchall():
        run_dict = dict(run)
        tid = run_dict['task_id']
        runs_by_task.setdefault(tid, []).append(run_dict)

    # Conteo de changes_requested
    cur = conn.execute(
        f"SELECT task_id, count(*) as cnt FROM task_events "
        f"WHERE kind='changes_requested' AND task_id IN ({placeholders}) "
        f"GROUP BY task_id",
        task_ids,
    )
    changes_by_task = {row['task_id']: row['cnt'] for row in cur.fetchall()}

    # Enriquecer tasks con métricas calculadas
    for task in group_tasks:
        tid = task['id']
        runs = runs_by_task.get(tid, [])
        task['runs'] = runs
        task['run_count'] = len(runs)
        task['changes_requested_count'] = changes_by_task.get(tid, 0)
        task['failure_count'] = sum(
            1 for r in runs if r.get('outcome') in FAILURE_OUTCOMES
        )
        task['total_duration_seconds'] = sum(
            (r['ended_at'] or 0) - (r['started_at'] or 0)
            for r in runs
            if r.get('started_at') and r.get('ended_at')
        )

    # Links intra-grupo
    cur = conn.execute(
        f'SELECT parent_id, child_id FROM task_links '
        f'WHERE parent_id IN ({placeholders}) AND child_id IN ({placeholders})',
        task_ids + task_ids,
    )
    links = [dict(row) for row in cur.fetchall()]

    return {'key': key, 'tasks': group_tasks, 'links': links}


def api_task(
    conn: sqlite3.Connection, known_cols: set, task_id: str
) -> dict | None:
    """GET /api/tasks/{id} — Detalle completo de una task."""
    extra = [c for c in OPTIONAL_COLS if c in known_cols]
    col_list = ', '.join(list(REQUIRED_TASK_COLS) + extra)

    cur = conn.execute(
        f'SELECT {col_list} FROM tasks WHERE id = ?', [task_id]
    )
    row = cur.fetchone()
    if row is None:
        return None
    task = dict(row)

    # Comentarios (orden cronológico)
    cur = conn.execute(
        'SELECT id, author, body, created_at FROM task_comments '
        'WHERE task_id = ? ORDER BY id',
        [task_id],
    )
    task['comments'] = [dict(r) for r in cur.fetchall()]

    # Eventos (max 50, sin heartbeats, más recientes primero)
    cur = conn.execute(
        "SELECT id, kind, payload, created_at FROM task_events "
        "WHERE task_id = ? AND kind != 'heartbeat' "
        "ORDER BY id DESC LIMIT 50",
        [task_id],
    )
    task['events'] = [dict(r) for r in cur.fetchall()]

    # Runs
    cur = conn.execute(
        'SELECT id, outcome, started_at, ended_at, profile '
        'FROM task_runs WHERE task_id = ?',
        [task_id],
    )
    runs = [dict(r) for r in cur.fetchall()]
    task['runs'] = runs
    task['run_count'] = len(runs)
    task['failure_count'] = sum(
        1 for r in runs if r.get('outcome') in FAILURE_OUTCOMES
    )

    # changes_requested
    cur = conn.execute(
        "SELECT count(*) as cnt FROM task_events "
        "WHERE kind='changes_requested' AND task_id = ?",
        [task_id],
    )
    task['changes_requested_count'] = cur.fetchone()['cnt']

    task['total_duration_seconds'] = sum(
        (r['ended_at'] or 0) - (r['started_at'] or 0)
        for r in runs
        if r.get('started_at') and r.get('ended_at')
    )

    return task


# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------

class KanbanHandler(BaseHTTPRequestHandler):
    """Maneja peticiones HTTP para el visor. El servidor inyecta conn y cols."""

    def do_GET(self):
        path = self.path.split('?')[0]

        if path in ('/', '/index.html'):
            self._serve_index()
        elif path == '/api/groups':
            data = api_groups(self.server.conn, self.server.known_cols)
            self._json(200, data)
        elif m := re.match(r'^/api/group/(.+)$', path):
            key = unquote(m.group(1))
            data = api_group(self.server.conn, self.server.known_cols, key)
            if data is None:
                self._json(404, {'error': 'not found'})
            else:
                self._json(200, data)
        elif m := re.match(r'^/api/tasks/(.+)$', path):
            task_id = unquote(m.group(1))
            data = api_task(self.server.conn, self.server.known_cols, task_id)
            if data is None:
                self._json(404, {'error': 'not found'})
            else:
                self._json(200, data)
        else:
            self._json(404, {'error': 'not found'})

    def _json(self, code: int, data) -> None:
        body = json.dumps(data, default=str).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_index(self) -> None:
        index_path = pathlib.Path(__file__).parent / 'index.html'
        try:
            content = index_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404, 'index.html not found')

    def log_message(self, format, *args):  # noqa: A002
        # Silenciar el log de cada request para no saturar la consola
        print(f'[visor] {self.address_string()} {format % args}', file=sys.stderr)


class KanbanServer(HTTPServer):
    """HTTPServer extendido con conexión a la DB y columnas conocidas."""

    def __init__(
        self,
        server_address: tuple,
        RequestHandlerClass,
        db_path: str,
    ):
        super().__init__(server_address, RequestHandlerClass)
        self.conn = open_db(db_path)
        self.known_cols = get_task_cols(self.conn)


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8787))
    db_path = find_db()

    print(f'[visor] DB: {db_path}', file=sys.stderr)
    print(f'[visor] Iniciando en http://127.0.0.1:{port}', file=sys.stderr)

    server_instance = KanbanServer(('127.0.0.1', port), KanbanHandler, db_path)
    try:
        server_instance.serve_forever()
    except KeyboardInterrupt:
        print('\n[visor] Detenido.', file=sys.stderr)
    finally:
        server_instance.server_close()
        server_instance.conn.close()
