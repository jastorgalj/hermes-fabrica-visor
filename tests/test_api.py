"""
Tests de la API del visor-v1.
Todos los tests usan una DB SQLite temporal con el mismo esquema que kanban.db.
Sin dependencias externas: solo stdlib.
"""
import os
import sys
import pathlib
import sqlite3
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
