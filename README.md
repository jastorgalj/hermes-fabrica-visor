# fabrica-visor

Visor de solo lectura del flujo de la fabrica de agentes de Hermes (tablero kanban).
Muestra, por issue, el grafo de cards, el paso en que va, las iteraciones y las esperas de decision humana.

Parte de `hermes-tools/`: herramientas que desarrollamos para Hermes.

Estado: greenfield. El primer change de OpenSpec es `visor-v1` (ver `openspec/changes/`).

## Principios
- Solo lectura: nunca escribe en `kanban.db` ni en el tablero.
- Pagina aparte, con auto-refresco, y aspecto coherente con el dashboard de Hermes.
- La capa de datos (API) separada de la UI, para poder migrarla luego a plugin del dashboard de Hermes.
