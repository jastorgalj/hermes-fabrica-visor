"""
Tests de la API del visor-v1.
Todos los tests usan una DB SQLite temporal con el mismo esquema que kanban.db.
Sin dependencias externas: solo stdlib.
"""
import json
import os
import sys
import pathlib
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch

# Agregar el directorio padre al path para importar server
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import server


# ---------------------------------------------------------------------------
# Helpers para crear una DB temporal con el esquema completo
# ---------------------------------------------------------------------------

SCHEMA_FULL = """
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    assignee TEXT,
    status TEXT,
    block_kind TEXT,
    model_override TEXT,
    provider_override TEXT,
    created_at INTEGER,
    completed_at INTEGER
);
CREATE TABLE task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    profile TEXT,
    outcome TEXT,
    started_at INTEGER,
    ended_at INTEGER
);
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    run_id INTEGER,
    kind TEXT,
    payload TEXT,
    created_at INTEGER
);
CREATE TABLE task_links (
    parent_id TEXT,
    child_id TEXT
);
CREATE TABLE task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    author TEXT,
    body TEXT,
    created_at INTEGER
);
"""

SCHEMA_NO_OPTIONAL = """
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    assignee TEXT,
    status TEXT,
    created_at INTEGER,
    completed_at INTEGER
);
CREATE TABLE task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    profile TEXT,
    outcome TEXT,
    started_at INTEGER,
    ended_at INTEGER
);
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    run_id INTEGER,
    kind TEXT,
    payload TEXT,
    created_at INTEGER
);
CREATE TABLE task_links (
    parent_id TEXT,
    child_id TEXT
);
CREATE TABLE task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    author TEXT,
    body TEXT,
    created_at INTEGER
);
"""


def make_db(schema: str) -> tuple[str, sqlite3.Connection]:
    """Crea un archivo DB temporal con el schema dado. Retorna (path, conn)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.commit()
    return path, conn


def open_ro(path: str) -> tuple[sqlite3.Connection, set]:
    """Abre la DB en modo lectura y retorna (conn, known_cols)."""
    conn = server.open_db(path)
    known_cols = server.get_task_cols(conn)
    return conn, known_cols


# ---------------------------------------------------------------------------
# Tests de agrupacion (logica pura)
# ---------------------------------------------------------------------------

class TestGroupKey(unittest.TestCase):
    """Verifica que la extraccion del key del titulo es correcta."""

    def _key(self, title: str) -> str:
        import re
        m = re.match(r'^([^\s:]+)', title)
        return m.group(1) if m else '(sin-grupo)'

    def test_space_separator(self):
        self.assertEqual(self._key('MTD-357 backend: algo'), 'MTD-357')

    def test_colon_separator(self):
        self.assertEqual(self._key('trail-solo-grafo:algo'), 'trail-solo-grafo')

    def test_no_separator_returns_singrupo(self):
        # Titulo sin espacio ni dos puntos → el titulo completo es el primer token
        # El spec dice "(sin-grupo)" solo cuando no hay patrón; con un token unico
        # el patron matchea el token completo. Verificar que "singrupo" da "singrupo".
        self.assertEqual(self._key('singrupo'), 'singrupo')

    def test_empty_title_returns_singrupo(self):
        # Titulo vacio o None → (sin-grupo)
        import re
        m = re.match(r'^([^\s:]+)', '')
        key = m.group(1) if m else '(sin-grupo)'
        self.assertEqual(key, '(sin-grupo)')


# ---------------------------------------------------------------------------
# Tests de /api/groups
# ---------------------------------------------------------------------------

class TestApiGroups(unittest.TestCase):

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_FULL)
        self.wconn.executemany(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ('t1', 'MTD-357 backend: algo',  'coder',    'running', None, None, None, 1000, None),
                ('t2', 'MTD-357 frontend',        'coder',    'done',    None, None, None, 1000, 2000),
                ('t3', 'MTD-358 fix',             'coder',    'blocked', 'needs_input', None, None, 1000, None),
                ('t4', 'MTD-358 review',          'reviewer', 'blocked', 'dependency',  None, None, 1000, None),
                ('t5', 'trail-solo: spec',        'explorer', 'todo',    None, None, None, 1000, None),
                ('t6', 'archived-task',           'coder',    'archived',None, None, None, 1000, None),
            ]
        )
        self.wconn.commit()
        self.conn, self.known_cols = open_ro(self.path)

    def tearDown(self):
        self.conn.close()
        self.wconn.close()
        os.unlink(self.path)

    def test_groups_excludes_archived(self):
        groups = server.api_groups(self.conn, self.known_cols)
        keys = {g['key'] for g in groups}
        self.assertNotIn('archived-task', keys)

    def test_groups_structure(self):
        groups = server.api_groups(self.conn, self.known_cols)
        for g in groups:
            self.assertIn('key', g)
            self.assertIn('label', g)
            self.assertIn('task_count', g)
            self.assertIn('running_count', g)
            self.assertIn('blocked_input_count', g)

    def test_task_count(self):
        groups = server.api_groups(self.conn, self.known_cols)
        g357 = next(g for g in groups if g['key'] == 'MTD-357')
        self.assertEqual(g357['task_count'], 2)

    def test_running_count(self):
        groups = server.api_groups(self.conn, self.known_cols)
        g357 = next(g for g in groups if g['key'] == 'MTD-357')
        self.assertEqual(g357['running_count'], 1)

    def test_blocked_input_count(self):
        groups = server.api_groups(self.conn, self.known_cols)
        g358 = next(g for g in groups if g['key'] == 'MTD-358')
        # Solo la t3 (needs_input), no la t4 (dependency)
        self.assertEqual(g358['blocked_input_count'], 1)

    def test_groups_present(self):
        groups = server.api_groups(self.conn, self.known_cols)
        keys = {g['key'] for g in groups}
        self.assertIn('MTD-357', keys)
        self.assertIn('MTD-358', keys)
        self.assertIn('trail-solo', keys)


# ---------------------------------------------------------------------------
# Tests de /api/group/{key}
# ---------------------------------------------------------------------------

class TestApiGroup(unittest.TestCase):

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_FULL)
        self.wconn.executemany(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ('t1', 'MTD-360 explorar',   'explorer', 'done',    None, None, None, 1000, 2000),
                ('t2', 'MTD-360 implementar','coder',    'done',    None, 'claude-opus', None, 1001, 3000),
                ('t3', 'MTD-360 review',     'reviewer', 'running', None, None, None, 1002, None),
                ('t4', 'OTHER-1 algo',       'coder',    'running', None, None, None, 1003, None),
            ]
        )
        # Links: t1→t2, t2→t3 (intra-grupo). t1→t4 (cross-grupo, no debe aparecer)
        self.wconn.executemany(
            "INSERT INTO task_links VALUES (?,?)",
            [('t1', 't2'), ('t2', 't3'), ('t1', 't4')]
        )
        # Runs para t1: 1 done, 1 crashed
        self.wconn.executemany(
            "INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at) VALUES (?,?,?,?,?)",
            [
                ('t1', 'explorer', 'done',    1000, 1500),
                ('t1', 'explorer', 'crashed', 500,  600),
                ('t2', 'coder',    'done',    1001, 3000),
            ]
        )
        # Evento changes_requested para t3
        self.wconn.execute(
            "INSERT INTO task_events (task_id, kind, payload, created_at) VALUES (?,?,?,?)",
            ('t3', 'changes_requested', '{}', 2000)
        )
        self.wconn.commit()
        self.conn, self.known_cols = open_ro(self.path)

    def tearDown(self):
        self.conn.close()
        self.wconn.close()
        os.unlink(self.path)

    def test_group_returns_correct_tasks(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        self.assertIsNotNone(result)
        ids = {t['id'] for t in result['tasks']}
        self.assertEqual(ids, {'t1', 't2', 't3'})

    def test_group_links_intra_only(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        links = result['links']
        # Solo t1→t2 y t2→t3; no t1→t4 (t4 es de otro grupo)
        link_pairs = {(l['parent_id'], l['child_id']) for l in links}
        self.assertIn(('t1', 't2'), link_pairs)
        self.assertIn(('t2', 't3'), link_pairs)
        self.assertNotIn(('t1', 't4'), link_pairs)

    def test_run_count(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t1 = next(t for t in result['tasks'] if t['id'] == 't1')
        self.assertEqual(t1['run_count'], 2)

    def test_failure_count_crashed(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t1 = next(t for t in result['tasks'] if t['id'] == 't1')
        # t1 tiene 1 crashed
        self.assertEqual(t1['failure_count'], 1)

    def test_failure_count_multiple_kinds(self):
        # Agregar runs con todos los tipos de fallo
        self.wconn.executemany(
            "INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at) VALUES (?,?,?,?,?)",
            [
                ('t3', 'reviewer', 'rate_limited', 2000, 2100),
                ('t3', 'reviewer', 'reclaimed',    2100, 2200),
                ('t3', 'reviewer', 'gave_up',      2200, 2300),
            ]
        )
        self.wconn.commit()
        # Reabrir lectura
        self.conn.close()
        self.conn, self.known_cols = open_ro(self.path)
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t3 = next(t for t in result['tasks'] if t['id'] == 't3')
        self.assertEqual(t3['failure_count'], 3)  # rate_limited + reclaimed + gave_up

    def test_changes_requested_count(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t3 = next(t for t in result['tasks'] if t['id'] == 't3')
        self.assertEqual(t3['changes_requested_count'], 1)

    def test_total_duration_seconds(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t1 = next(t for t in result['tasks'] if t['id'] == 't1')
        # run1: 1500-1000=500, run2: 600-500=100 → total 600
        self.assertEqual(t1['total_duration_seconds'], 600)

    def test_runs_array_per_task(self):
        result = server.api_group(self.conn, self.known_cols, 'MTD-360')
        t1 = next(t for t in result['tasks'] if t['id'] == 't1')
        self.assertEqual(len(t1['runs']), 2)
        for r in t1['runs']:
            self.assertIn('id', r)
            self.assertIn('outcome', r)
            self.assertIn('started_at', r)
            self.assertIn('ended_at', r)
            self.assertIn('profile', r)

    def test_nonexistent_group_returns_none(self):
        result = server.api_group(self.conn, self.known_cols, 'NO-EXISTE')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests de /api/tasks/{id}
# ---------------------------------------------------------------------------

class TestApiTask(unittest.TestCase):

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_FULL)
        self.wconn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            ('t_abc', 'MTD-123 algo', 'coder', 'running', None, None, None, 1000, None)
        )
        # 3 comentarios
        self.wconn.executemany(
            "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?,?,?,?)",
            [('t_abc', 'user', f'comentario {i}', 1000+i) for i in range(3)]
        )
        # 60 eventos: 55 normales PRIMERO (ids más bajos) + 5 heartbeat DESPUÉS (ids altos).
        # Con ORDER BY id DESC: los heartbeats quedan en el TOP-5.
        # → Sin filtro AND kind!='heartbeat', los heartbeats ENTRAN en el LIMIT 50
        #   → test_events_exclude_heartbeat falla (rojo real).
        # → Sin LIMIT, los 55 normales se retornan todos
        #   → test_events_max_50 falla (55 > 50, rojo real).
        events = []
        for i in range(55):
            events.append(('t_abc', None, 'created', '{}', 1000+i))
        for i in range(5):
            events.append(('t_abc', None, 'heartbeat', '{}', 2000+i))
        self.wconn.executemany(
            "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) VALUES (?,?,?,?,?)",
            events
        )
        # 2 runs: 1 done, 1 gave_up
        self.wconn.executemany(
            "INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at) VALUES (?,?,?,?,?)",
            [('t_abc', 'coder', 'done', 1000, 2000), ('t_abc', 'coder', 'gave_up', 500, 600)]
        )
        self.wconn.commit()
        self.conn, self.known_cols = open_ro(self.path)

    def tearDown(self):
        self.conn.close()
        self.wconn.close()
        os.unlink(self.path)

    def test_nonexistent_returns_none(self):
        result = server.api_task(self.conn, self.known_cols, 't_noexiste')
        self.assertIsNone(result)

    def test_existing_returns_task(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        self.assertIsNotNone(result)
        self.assertEqual(result['id'], 't_abc')
        self.assertEqual(result['title'], 'MTD-123 algo')

    def test_comments_included(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        self.assertEqual(len(result['comments']), 3)

    def test_events_exclude_heartbeat(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        for ev in result['events']:
            self.assertNotEqual(ev['kind'], 'heartbeat')

    def test_events_max_50(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        # 55 normales filtrados a LIMIT 50 → exactamente 50
        self.assertEqual(len(result['events']), 50)

    def test_events_newest_first(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        ids = [ev['id'] for ev in result['events']]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_run_count(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        self.assertEqual(result['run_count'], 2)

    def test_failure_count(self):
        result = server.api_task(self.conn, self.known_cols, 't_abc')
        # 1 gave_up → failure_count = 1
        self.assertEqual(result['failure_count'], 1)


# ---------------------------------------------------------------------------
# Test de apertura en modo solo lectura
# ---------------------------------------------------------------------------

class TestReadOnly(unittest.TestCase):

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_FULL)
        self.wconn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            ('t1', 'test', 'coder', 'done', None, None, None, 1000, None)
        )
        self.wconn.commit()
        self.wconn.close()
        self.conn = server.open_db(self.path)

    def tearDown(self):
        self.conn.close()
        os.unlink(self.path)

    def test_insert_raises_operational_error(self):
        """La conexión mode=ro debe rechazar INSERT con OperationalError."""
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute(
                "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
                ('t_evil', 'evil', 'evil', 'evil', None, None, None, 0, None)
            )

    def test_update_raises_operational_error(self):
        """La conexión mode=ro debe rechazar UPDATE con OperationalError."""
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute("UPDATE tasks SET title='hacked' WHERE id='t1'")


# ---------------------------------------------------------------------------
# Tests de columnas opcionales ausentes
# ---------------------------------------------------------------------------

class TestAbsentOptionalColumns(unittest.TestCase):
    """DB sin block_kind, model_override, provider_override en tasks."""

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_NO_OPTIONAL)
        self.wconn.executemany(
            "INSERT INTO tasks (id, title, assignee, status, created_at) VALUES (?,?,?,?,?)",
            [
                ('t1', 'MTD-100 algo', 'coder', 'running', 1000),
                ('t2', 'MTD-100 mas',  'coder', 'done',    1001),
            ]
        )
        self.wconn.commit()
        self.conn, self.known_cols = open_ro(self.path)

    def tearDown(self):
        self.conn.close()
        self.wconn.close()
        os.unlink(self.path)

    def test_api_groups_no_error_without_optional_cols(self):
        """api_groups no debe lanzar error aunque falten columnas opcionales."""
        result = server.api_groups(self.conn, self.known_cols)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['key'], 'MTD-100')

    def test_api_groups_blocked_input_count_zero_without_block_kind(self):
        """Sin block_kind en el schema, blocked_input_count debe ser 0."""
        result = server.api_groups(self.conn, self.known_cols)
        self.assertEqual(result[0]['blocked_input_count'], 0)

    def test_api_group_no_error_without_optional_cols(self):
        """api_group no debe lanzar error aunque falten columnas opcionales."""
        result = server.api_group(self.conn, self.known_cols, 'MTD-100')
        self.assertIsNotNone(result)
        self.assertEqual(len(result['tasks']), 2)

    def test_api_task_no_error_without_optional_cols(self):
        """api_task no debe lanzar error aunque falten columnas opcionales."""
        result = server.api_task(self.conn, self.known_cols, 't1')
        self.assertIsNotNone(result)
        self.assertNotIn('block_kind', result)
        self.assertNotIn('model_override', result)

    def test_known_cols_does_not_include_absent_cols(self):
        """get_task_cols no debe incluir columnas que no existen en el schema."""
        self.assertNotIn('block_kind', self.known_cols)
        self.assertNotIn('model_override', self.known_cols)
        self.assertNotIn('provider_override', self.known_cols)


# ---------------------------------------------------------------------------
# Tests de find_db
# ---------------------------------------------------------------------------

class TestFindDb(unittest.TestCase):

    def setUp(self):
        # Guardar env vars originales
        self._orig_kanban_db = os.environ.get('KANBAN_DB')
        self._orig_localappdata = os.environ.get('LOCALAPPDATA')

    def tearDown(self):
        # Restaurar env vars
        if self._orig_kanban_db is not None:
            os.environ['KANBAN_DB'] = self._orig_kanban_db
        elif 'KANBAN_DB' in os.environ:
            del os.environ['KANBAN_DB']

        if self._orig_localappdata is not None:
            os.environ['LOCALAPPDATA'] = self._orig_localappdata
        elif 'LOCALAPPDATA' in os.environ:
            del os.environ['LOCALAPPDATA']

    def test_kanban_db_env_takes_priority(self):
        """KANBAN_DB env tiene maxima prioridad."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            os.environ['KANBAN_DB'] = path
            result = server.find_db()
            self.assertEqual(result, path)
        finally:
            os.unlink(path)

    def test_localappdata_fallback(self):
        """Sin KANBAN_DB, usa %LOCALAPPDATA%\\hermes\\kanban.db si existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            hermes_dir = os.path.join(tmpdir, 'hermes')
            os.makedirs(hermes_dir)
            db_path = os.path.join(hermes_dir, 'kanban.db')
            # Crear archivo vacío para que pathlib.Path.exists() retorne True
            open(db_path, 'w').close()

            if 'KANBAN_DB' in os.environ:
                del os.environ['KANBAN_DB']
            os.environ['LOCALAPPDATA'] = tmpdir

            result = server.find_db()
            self.assertEqual(result, db_path)

    def test_no_db_found_raises_systemexit(self):
        """Si ninguna ruta existe, find_db llama sys.exit (lanza SystemExit)."""
        # Apuntar todas las rutas a paths inexistentes
        os.environ['KANBAN_DB'] = '/nonexistent/absolutely/kanban.db'
        os.environ['LOCALAPPDATA'] = '/nonexistent'
        # Mockear Path.home para que ~/.hermes/kanban.db tampoco exista
        fake_home = pathlib.Path('/nonexistent/home')
        with patch.object(pathlib.Path, 'home', return_value=fake_home):
            with self.assertRaises(SystemExit) as ctx:
                server.find_db()
            # Debe salir con código no-cero
            self.assertNotEqual(ctx.exception.code, 0)


# ---------------------------------------------------------------------------
# Tests de decodificación URL en los endpoints HTTP
# ---------------------------------------------------------------------------

class TestUrlDecodingHttp(unittest.TestCase):
    """
    Los endpoints /api/group/{key} y /api/tasks/{id} deben decodificar
    caracteres URL-encoded en el segmento del path antes de buscar en la DB.

    Protocolo TDD:
      RED  → sin unquote en server.py, el test falla (404 en vez de 200).
      GREEN → con unquote, el test pasa.
    """

    @classmethod
    def setUpClass(cls):
        cls.db_path, cls.wconn = make_db(SCHEMA_FULL)
        # Grupo cuya clave contiene <, > y &  (el título incluye espacio natural)
        # _group_key('<b>XSS</b>&test explorar') → '<b>XSS</b>&test'
        # Task ID con espacio para probar unquote en /api/tasks/{id}
        cls.wconn.executemany(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            [
                ('t_sp ec ial',
                 '<b>XSS</b>&test explorar',
                 'coder', 'running', None, None, None, 1000, None),
                ('t_normal',
                 'MTD-360 explorar',
                 'coder', 'done', None, None, None, 1001, 2000),
            ]
        )
        cls.wconn.commit()

        from server import KanbanServer, KanbanHandler
        # Crear el servidor DENTRO del hilo que sirve, para que la conexión
        # SQLite (mode=ro) se abra y se use en el mismo hilo. Así no hace falta
        # check_same_thread=False en producción: solo se ejercita el unquote.
        ready = threading.Event()
        holder = {}

        def _serve():
            srv = KanbanServer(('127.0.0.1', 0), KanbanHandler, cls.db_path)
            holder['srv'] = srv
            holder['port'] = srv.server_address[1]
            ready.set()
            try:
                srv.serve_forever()
            finally:
                # cerrar en el MISMO hilo en que se abrieron (mode=ro)
                srv.server_close()
                srv.conn.close()

        cls._srv_thread = threading.Thread(target=_serve, daemon=True)
        cls._srv_thread.start()
        if not ready.wait(10):
            raise RuntimeError('el servidor de test no arrancó')
        cls.srv = holder['srv']
        cls.port = holder['port']

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()              # detiene serve_forever (hilo servidor)
        cls._srv_thread.join(10)        # espera a que cierre conn/socket allí
        cls.wconn.close()
        os.unlink(cls.db_path)

    def _get(self, path):
        """HTTP GET al servidor de test; retorna (status_code, json_body)."""
        url = f'http://127.0.0.1:{self.port}{path}'
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    # --- /api/group/{key} ---

    def test_encoded_group_key_returns_200(self):
        """GET /api/group/<clave_codificada> → 200 con el grupo correcto."""
        # clave: '<b>XSS</b>&test'  →  '%3Cb%3EXSS%3C%2Fb%3E%26test'
        encoded = urllib.parse.quote('<b>XSS</b>&test', safe='')
        status, data = self._get(f'/api/group/{encoded}')
        self.assertEqual(status, 200)
        self.assertEqual(data['key'], '<b>XSS</b>&test')

    def test_nonexistent_encoded_key_returns_404_json(self):
        """GET /api/group/<clave_inexistente_codificada> → 404 JSON con 'error'."""
        encoded = urllib.parse.quote('<no-existe>&missing', safe='')
        status, data = self._get(f'/api/group/{encoded}')
        self.assertEqual(status, 404)
        self.assertIn('error', data)

    def test_normal_group_key_unaffected(self):
        """Claves normales sin encoding especial siguen funcionando."""
        status, data = self._get('/api/group/MTD-360')
        self.assertEqual(status, 200)
        self.assertEqual(data['key'], 'MTD-360')

    # --- /api/tasks/{id} ---

    def test_encoded_task_id_returns_task(self):
        """GET /api/tasks/<id_codificado> → 200 con la task correcta."""
        # id: 't_sp ec ial'  →  't_sp%20ec%20ial'
        encoded = urllib.parse.quote('t_sp ec ial', safe='')
        status, data = self._get(f'/api/tasks/{encoded}')
        self.assertEqual(status, 200)
        self.assertEqual(data['id'], 't_sp ec ial')



# ---------------------------------------------------------------------------
# Schema con columnas summary/metadata en task_runs (para tests de timeline)
# ---------------------------------------------------------------------------

SCHEMA_WITH_RUN_META = """\
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT,
    assignee TEXT,
    status TEXT,
    block_kind TEXT,
    model_override TEXT,
    provider_override TEXT,
    created_at INTEGER,
    completed_at INTEGER
);
CREATE TABLE task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    profile TEXT,
    outcome TEXT,
    summary TEXT,
    metadata TEXT,
    started_at INTEGER,
    ended_at INTEGER
);
CREATE TABLE task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    run_id INTEGER,
    kind TEXT,
    payload TEXT,
    created_at INTEGER
);
CREATE TABLE task_links (
    parent_id TEXT,
    child_id TEXT
);
CREATE TABLE task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    author TEXT,
    body TEXT,
    created_at INTEGER
);
"""


# ---------------------------------------------------------------------------
# Tests de find_logs_dir  (Unit-LOG-04)
# ---------------------------------------------------------------------------

class TestFindLogsDir(unittest.TestCase):

    def setUp(self):
        self._orig = os.environ.get('KANBAN_LOGS_DIR')

    def tearDown(self):
        if self._orig is not None:
            os.environ['KANBAN_LOGS_DIR'] = self._orig
        elif 'KANBAN_LOGS_DIR' in os.environ:
            del os.environ['KANBAN_LOGS_DIR']

    def test_kanban_logs_dir_env_takes_priority(self):
        """Unit-LOG-04: KANBAN_LOGS_DIR definida → se usa y se ignora la por defecto."""
        os.environ['KANBAN_LOGS_DIR'] = '/custom/logs/dir'
        result = server.find_logs_dir('/ignored/path/kanban.db')
        self.assertEqual(result, '/custom/logs/dir')

    def test_default_fallback_dirname_kanban_logs(self):
        """Sin KANBAN_LOGS_DIR, usa {dirname(db_path)}/kanban/logs."""
        if 'KANBAN_LOGS_DIR' in os.environ:
            del os.environ['KANBAN_LOGS_DIR']
        result = server.find_logs_dir('/some/path/kanban.db')
        expected = str(pathlib.Path('/some/path') / 'kanban' / 'logs')
        self.assertEqual(result, expected)


# ---------------------------------------------------------------------------
# Tests de api_task_worker_log  (Unit-LOG-01..03)
# ---------------------------------------------------------------------------

class TestApiWorkerLog(unittest.TestCase):

    def setUp(self):
        self.logs_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.logs_dir, ignore_errors=True)

    def _write_log(self, task_id: str, lines: list):
        log_path = pathlib.Path(self.logs_dir) / f'{task_id}.log'
        log_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_tail_returns_last_n_lines_and_truncated(self):
        """Unit-LOG-01: tail=20 con archivo de 30 líneas → 20 últimas + truncated=True."""
        lines = [f'linea {i}' for i in range(1, 31)]
        self._write_log('t_a1b2c3d4', lines)

        result = server.api_task_worker_log('t_a1b2c3d4', 20, self.logs_dir)

        self.assertIsNotNone(result)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['lines']), 20)
        self.assertEqual(result['lines'], lines[-20:])

    def test_nonexistent_file_returns_none(self):
        """Unit-LOG-02: archivo inexistente → None (404)."""
        result = server.api_task_worker_log('t_a1b2c3d4', 20, self.logs_dir)
        self.assertIsNone(result)

    def test_tail_clamped_to_min_1(self):
        """Unit-LOG-03: tail=0 → recortado a 1 (ultima linea)."""
        self._write_log('t_a1b2c3d4', ['a', 'b', 'c'])

        result = server.api_task_worker_log('t_a1b2c3d4', 0, self.logs_dir)

        self.assertIsNotNone(result)
        self.assertEqual(len(result['lines']), 1)
        self.assertEqual(result['lines'], ['c'])

    def test_tail_clamped_to_max_500(self):
        """Unit-LOG-03: tail=600 → recortado a 500; archivo chico → no truncado."""
        lines = [f'line {i}' for i in range(1, 10)]
        self._write_log('t_a1b2c3d4', lines)

        result = server.api_task_worker_log('t_a1b2c3d4', 600, self.logs_dir)

        self.assertIsNotNone(result)
        self.assertFalse(result['truncated'])
        self.assertEqual(len(result['lines']), 9)

    def test_exact_tail_no_truncated(self):
        """tail igual al número de líneas → truncated=False."""
        lines = ['a', 'b', 'c', 'd', 'e']
        self._write_log('t_a1b2c3d4', lines)

        result = server.api_task_worker_log('t_a1b2c3d4', 5, self.logs_dir)

        self.assertFalse(result['truncated'])
        self.assertEqual(result['lines'], lines)


# ---------------------------------------------------------------------------
# Tests de api_task_timeline  (Unit-TL-01..06, VAL-02 puro)
# ---------------------------------------------------------------------------

class TestApiTimeline(unittest.TestCase):

    TASK_ID = 't_a1b2c3d4'

    def setUp(self):
        self.path, self.wconn = make_db(SCHEMA_WITH_RUN_META)
        self.wconn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            (self.TASK_ID, 'MTD-TL algo', 'coder', 'done', None, None, None, 1000, 2000),
        )
        self.wconn.commit()

    def tearDown(self):
        self.wconn.close()
        os.unlink(self.path)

    def _ro(self):
        return server.open_db(self.path)

    # --- Unit-VAL-02 (puro) ---

    def test_nonexistent_task_returns_none(self):
        """Unit-VAL-02: t_00000000 (hex válido, no en DB) → None (404)."""
        conn = self._ro()
        result = server.api_task_timeline(conn, 't_00000000')
        conn.close()
        self.assertIsNone(result)

    # --- Unit-TL-05 ---

    def test_run_no_ended_at_no_run_end_item(self):
        """Unit-TL-05: run con ended_at=null → run_start pero NO run_end."""
        self.wconn.execute(
            "INSERT INTO task_runs (task_id, profile, outcome, started_at, ended_at)"
            " VALUES (?,?,?,?,?)",
            (self.TASK_ID, 'coder', 'running', 1000, None),
        )
        self.wconn.commit()
        conn = self._ro()
        result = server.api_task_timeline(conn, self.TASK_ID)
        conn.close()

        types = [i['type'] for i in result['items']]
        self.assertIn('run_start', types)
        self.assertNotIn('run_end', types)

    # --- Unit-TL-02 ---

    def test_heartbeat_count_independent_of_filter(self):
        """Unit-TL-02: heartbeat_count=50 cuando hay 50 heartbeats, sin importar heartbeats=."""
        for i in range(50):
            self.wconn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
                " VALUES (?,?,?,?,?)",
                (self.TASK_ID, None, 'heartbeat', '{}', 2000 + i),
            )
        for i in range(3):
            self.wconn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
                " VALUES (?,?,?,?,?)",
                (self.TASK_ID, None, 'created', '{}', 1000 + i),
            )
        self.wconn.commit()
        conn = self._ro()

        r_no  = server.api_task_timeline(conn, self.TASK_ID, heartbeats=False)
        r_yes = server.api_task_timeline(conn, self.TASK_ID, heartbeats=True)
        conn.close()

        self.assertEqual(r_no['heartbeat_count'],  50)
        self.assertEqual(r_yes['heartbeat_count'], 50)
        for item in r_no['items']:
            if item['type'] == 'event':
                self.assertNotEqual(item.get('kind'), 'heartbeat')

    # --- Filtro heartbeats con id alto dentro del limit ---

    def test_heartbeat_excluded_high_id_within_limit(self):
        """Heartbeat con ts dentro del rango pero id alto → excluido con heartbeats=False."""
        for ts in [100, 200, 300]:  # ids 1,2,3
            self.wconn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
                " VALUES (?,?,?,?,?)",
                (self.TASK_ID, None, 'created', '{}', ts),
            )
        # heartbeat a ts=150, id=4 (cae dentro del rango cronológico)
        self.wconn.execute(
            "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
            " VALUES (?,?,?,?,?)",
            (self.TASK_ID, None, 'heartbeat', '{}', 150),
        )
        self.wconn.commit()
        conn = self._ro()

        result = server.api_task_timeline(conn, self.TASK_ID, limit=10, heartbeats=False)
        conn.close()

        self.assertEqual(result['heartbeat_count'], 1)
        self.assertEqual(len(result['items']), 3)
        self.assertFalse(result['truncated'])
        for item in result['items']:
            if item['type'] == 'event':
                self.assertNotEqual(item.get('kind'), 'heartbeat')

    # --- Unit-TL-03 ---

    def test_truncated_true_with_small_limit(self):
        """Unit-TL-03: truncated=True con limit=2 y 3 items reales."""
        for i in range(3):
            self.wconn.execute(
                "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
                " VALUES (?,?,?,?,?)",
                (self.TASK_ID, None, 'created', '{}', 1000 + i),
            )
        self.wconn.commit()
        conn = self._ro()

        result = server.api_task_timeline(conn, self.TASK_ID, limit=2)
        conn.close()

        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['items']), 2)

    # --- Unit-TL-01 ---

    def test_chronological_order_tie_breaking(self):
        """Unit-TL-01: mismo ts en 3 tablas → (ts, table_priority, row_id).

        Escenario sensible:
          - 4 runs dummy (ids 1-4) a ts distintos
          - run real a ts=TS → id=5 (alto)
          - comment a ts=TS → id=1
          - event  a ts=TS → id=1
        Sin table_priority: sort por (ts, rid) pondría event(1) y comment(1) ANTES
        que run_start(5), rompiendo el orden run→comment→event.
        """
        TS = 1000
        # 4 runs dummy para que el run real obtenga id=5
        for dummy_ts in [100, 200, 300, 400]:
            self.wconn.execute(
                "INSERT INTO task_runs"
                " (task_id, profile, outcome, summary, metadata, started_at, ended_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (self.TASK_ID, 'coder', 'done', None, None, dummy_ts, dummy_ts + 10),
            )
        # Run real a ts=TS → id=5
        self.wconn.execute(
            "INSERT INTO task_runs"
            " (task_id, profile, outcome, summary, metadata, started_at, ended_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.TASK_ID, 'coder', 'done', None, None, TS, TS + 500),
        )
        # comment a ts=TS → id=1 (primer comentario)
        self.wconn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at)"
            " VALUES (?,?,?,?)",
            (self.TASK_ID, 'user', 'comentario', TS),
        )
        # event a ts=TS → id=1 (primer evento)
        self.wconn.execute(
            "INSERT INTO task_events (task_id, run_id, kind, payload, created_at)"
            " VALUES (?,?,?,?,?)",
            (self.TASK_ID, None, 'created', '{}', TS),
        )
        self.wconn.commit()
        conn = self._ro()
        result = server.api_task_timeline(conn, self.TASK_ID)
        conn.close()

        # Filtrar solo los items a ts=TS
        at_ts = [i for i in result['items'] if i['ts'] == TS]
        # Esperamos: run_start, event, comment (prioridad 0, 1, 2 según design.md)
        types = [i['type'] for i in at_ts]
        self.assertIn('run_start', types)
        self.assertIn('comment',   types)
        self.assertIn('event',     types)
        # El primer item a ts=TS debe ser run_start (table_priority=0, aunque _rid=5)
        self.assertEqual(at_ts[0]['type'], 'run_start')
        self.assertEqual(at_ts[1]['type'], 'event')
        self.assertEqual(at_ts[2]['type'], 'comment')

    # --- Unit-TL-04 ---

    def test_metadata_excerpt_only_5_keys(self):
        """Unit-TL-04: metadata_excerpt devuelve exactamente las 5 claves previstas."""
        meta = json.dumps({
            'verification': 'ok',
            'friccion': [],
            'commit_message': 'feat: algo',
            'commit_message_source': 'manual',
            'review_outcome': 'approved',
            'extra_key': 'NO_DEBE_APARECER',
            'otra_extra': 42,
        })
        self.wconn.execute(
            "INSERT INTO task_runs"
            " (task_id, profile, outcome, summary, metadata, started_at, ended_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.TASK_ID, 'coder', 'done', 'sum', meta, 1000, 1500),
        )
        self.wconn.commit()
        conn = self._ro()
        result = server.api_task_timeline(conn, self.TASK_ID)
        conn.close()

        run_end = next(i for i in result['items'] if i['type'] == 'run_end')
        excerpt = run_end['metadata_excerpt']
        ALLOWED = {
            'verification', 'friccion', 'commit_message',
            'commit_message_source', 'review_outcome',
        }
        self.assertLessEqual(set(excerpt.keys()), ALLOWED)
        self.assertNotIn('extra_key', excerpt)
        self.assertNotIn('otra_extra', excerpt)

    # --- Unit-TL-06 ---

    def test_summary_truncated_to_500_chars(self):
        """Unit-TL-06: summary de 800 chars → summary del run_end truncado a 500."""
        self.wconn.execute(
            "INSERT INTO task_runs"
            " (task_id, profile, outcome, summary, metadata, started_at, ended_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.TASK_ID, 'coder', 'done', 'x' * 800, '{}', 1000, 1500),
        )
        self.wconn.commit()
        conn = self._ro()
        result = server.api_task_timeline(conn, self.TASK_ID)
        conn.close()

        run_end = next(i for i in result['items'] if i['type'] == 'run_end')
        self.assertEqual(len(run_end['summary']), 500)

    # --- Columna ausente → no 500 ---

    def test_missing_run_summary_metadata_no_500(self):
        """Columnas summary/metadata ausentes en task_runs → respuesta sin esos campos, nunca 500."""
        path2, wconn2 = make_db(SCHEMA_FULL)
        wconn2.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            (self.TASK_ID, 'MTD-TL', 'coder', 'done', None, None, None, 1000, 2000),
        )
        wconn2.execute(
            "INSERT INTO task_runs"
            " (task_id, profile, outcome, started_at, ended_at)"
            " VALUES (?,?,?,?,?)",
            (self.TASK_ID, 'coder', 'done', 1000, 1500),
        )
        wconn2.commit()
        wconn2.close()
        conn2 = server.open_db(path2)

        result = server.api_task_timeline(conn2, self.TASK_ID)
        conn2.close()
        os.unlink(path2)

        self.assertIsNotNone(result)
        run_end = next(i for i in result['items'] if i['type'] == 'run_end')
        self.assertNotIn('summary', run_end)
        self.assertNotIn('metadata_excerpt', run_end)


# ---------------------------------------------------------------------------
# Tests HTTP de /timeline y /worker-log  (Unit-VAL-01, VAL-02 via HTTP)
# ---------------------------------------------------------------------------

class TestTimelineAndWorkerLogHttp(unittest.TestCase):
    """Integración HTTP para los nuevos endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.db_path, cls.wconn = make_db(SCHEMA_WITH_RUN_META)
        cls.logs_tmpdir = tempfile.mkdtemp()

        cls.wconn.execute(
            "INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
            ('t_a1b2c3d4', 'MTD-HTTP test', 'coder', 'done', None, None, None, 1000, 2000),
        )
        cls.wconn.execute(
            "INSERT INTO task_runs"
            " (task_id, profile, outcome, summary, metadata, started_at, ended_at)"
            " VALUES (?,?,?,?,?,?,?)",
            ('t_a1b2c3d4', 'coder', 'done', 'run summary', '{}', 1000, 1500),
        )
        cls.wconn.execute(
            "INSERT INTO task_events"
            " (task_id, run_id, kind, payload, created_at) VALUES (?,?,?,?,?)",
            ('t_a1b2c3d4', 1, 'created', '{}', 900),
        )
        cls.wconn.execute(
            "INSERT INTO task_events"
            " (task_id, run_id, kind, payload, created_at) VALUES (?,?,?,?,?)",
            ('t_a1b2c3d4', None, 'heartbeat', '{}', 950),
        )
        cls.wconn.commit()

        # Archivo de log (10 lineas)
        log_path = pathlib.Path(cls.logs_tmpdir) / 't_a1b2c3d4.log'
        log_path.write_text(
            '\n'.join([f'linea {i}' for i in range(1, 11)]) + '\n',
            encoding='utf-8',
        )

        # Setear env ANTES de crear el servidor (find_logs_dir lo lee al init)
        cls._orig_logs_dir = os.environ.get('KANBAN_LOGS_DIR')
        os.environ['KANBAN_LOGS_DIR'] = cls.logs_tmpdir

        from server import KanbanServer, KanbanHandler
        ready = threading.Event()
        holder = {}

        def _serve():
            srv = KanbanServer(('127.0.0.1', 0), KanbanHandler, cls.db_path)
            holder['srv'] = srv
            holder['port'] = srv.server_address[1]
            ready.set()
            try:
                srv.serve_forever()
            finally:
                srv.server_close()
                srv.conn.close()

        cls._srv_thread = threading.Thread(target=_serve, daemon=True)
        cls._srv_thread.start()
        if not ready.wait(10):
            raise RuntimeError('El servidor de test no arrancó')
        cls.srv = holder['srv']
        cls.port = holder['port']

    @classmethod
    def tearDownClass(cls):
        if cls._orig_logs_dir is not None:
            os.environ['KANBAN_LOGS_DIR'] = cls._orig_logs_dir
        elif 'KANBAN_LOGS_DIR' in os.environ:
            del os.environ['KANBAN_LOGS_DIR']
        cls.srv.shutdown()
        cls._srv_thread.join(10)
        cls.wconn.close()
        os.unlink(cls.db_path)
        import shutil
        shutil.rmtree(cls.logs_tmpdir, ignore_errors=True)

    def _get(self, path):
        url = f'http://127.0.0.1:{self.port}{path}'
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    # --- Timeline ---

    def test_timeline_200_valid_task(self):
        status, data = self._get('/api/tasks/t_a1b2c3d4/timeline')
        self.assertEqual(status, 200)
        self.assertIn('items', data)
        self.assertIn('heartbeat_count', data)
        self.assertIn('truncated', data)
        self.assertIn('task_id', data)

    def test_timeline_heartbeat_count_always_present_and_items_filtered(self):
        """heartbeat_count=1 siempre; items sin heartbeats con heartbeats=false."""
        status, data = self._get('/api/tasks/t_a1b2c3d4/timeline')
        self.assertEqual(status, 200)
        self.assertEqual(data['heartbeat_count'], 1)
        for item in data['items']:
            if item.get('type') == 'event':
                self.assertNotEqual(item.get('kind'), 'heartbeat')

    def test_timeline_404_nonexistent_task(self):
        """Unit-VAL-02: t_00000000/timeline (hex válido, no en DB) → 404."""
        status, data = self._get('/api/tasks/t_00000000/timeline')
        self.assertEqual(status, 404)
        self.assertIn('error', data)

    def test_timeline_nonhex_id_still_404_not_400(self):
        """Timeline NO aplica regex; id no-hex → 404 (resolución contra DB)."""
        status, _ = self._get('/api/tasks/t_inexistente/timeline')
        self.assertEqual(status, 404)

    # --- Worker log ---

    def test_worker_log_200_valid_task(self):
        status, data = self._get('/api/tasks/t_a1b2c3d4/worker-log')
        self.assertEqual(status, 200)
        self.assertIn('lines', data)
        self.assertIn('truncated', data)
        self.assertIn('task_id', data)

    def test_worker_log_400_invalid_id(self):
        """Id no-hex en worker-log → 400."""
        status, data = self._get('/api/tasks/t_xss_test_001/worker-log')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error'), 'invalid task_id')

    def test_worker_log_400_path_traversal(self):
        """Unit-VAL-01: traversal codificado → 400 invalid task_id."""
        traversal = urllib.parse.quote('../../etc/passwd', safe='')
        status, data = self._get(f'/api/tasks/{traversal}/worker-log')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error'), 'invalid task_id')

    def test_worker_log_400_newline_in_id(self):
        """B1: id con newline codificado (%0a) → 400 invalid task_id.
        Con TASK_ID_RE.match() '$' acepta '\\n' y el id pasa el filtro → 404.
        Con fullmatch() el '\\n' queda fuera del patrón → 400 correcto.
        """
        # t_abc%0a → unquote → 't_abc\n' → no es hex válido → 400
        status, data = self._get('/api/tasks/t_abc%0a/worker-log')
        self.assertEqual(status, 400)
        self.assertEqual(data.get('error'), 'invalid task_id')

    def test_worker_log_404_valid_hex_not_in_db(self):
        """Id hex válido pero no en DB → 404."""
        status, _ = self._get('/api/tasks/t_00000000/worker-log')
        self.assertEqual(status, 404)

    def test_worker_log_tail_param(self):
        """tail=5 con archivo de 10 líneas → 5 líneas, truncated=True."""
        status, data = self._get('/api/tasks/t_a1b2c3d4/worker-log?tail=5')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['lines']), 5)
        self.assertTrue(data['truncated'])


if __name__ == '__main__':
    unittest.main()
