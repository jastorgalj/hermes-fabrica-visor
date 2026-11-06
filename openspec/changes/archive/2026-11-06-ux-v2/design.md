# Design

## Skip: no aplica

Ninguna de las condiciones del artifact design aplica a este change:
- Sin cambio de modelo de datos ni esquema de BD.
- Sin dependencias nuevas (Python stdlib + HTML vanilla).
- Sin decisiones de arquitectura pendientes: los cambios son a una función JS
  (`drawArrows`, index.html:L1158) y a variables CSS en `:root` (index.html:L70).
- Sin complejidad de migración, seguridad o rendimiento que requiera diseño previo.

Decision de orquestador (corrige la propuesta del explorer): NO hay tension minima de 80 px.
El espacio entre columnas es 48 px y 80 px cruzaria los controles; ademas, con los extremos a
la misma altura una Bezier con control horizontal es una recta, por geometria. La mejora de
los conectores es trazo 2.5 px, punta 10x8, llegada separada 10 px por conector entrante y
color por estado.

## Por que se recalculan las derivadas del tema
Si solo se cambian 4 variables, el sidebar, el header y los paneles siguen verdes
(`--color-sidebar-bg`, `--color-header-bg`, etc. derivaban del teal) y el visor queda a
medio camino respecto de Hermes desktop.

## Punta de flecha por estado (decision del orquestador tras review ronda 1)
`path.style.color` + `fill="currentColor"` en un unico marker NO es fiable: el contenido de un `<marker>` hereda de sus ancestros DOM, no del path que lo referencia. Se usa un marker por estado (`arrowhead-done`, `-running`, `-blocked`, `-neutral`), cada uno 10x8 con `points="0 0, 10 4, 0 8"`, y su color por regla CSS (`#arrowhead-done polygon { fill: var(--color-arrow-done) }`), sin literales y sin depender de context-stroke.

## Variable --color-accent-text (decision del orquestador tras review ronda 2)
`--color-accent: #4c89ff` da 4.16:1 sobre `surface-2` (#272d3a) como texto, insuficiente. El
acento no puede cambiar (viene de Hermes desktop). Se agrega `--color-accent-text: #5891ff`
(mismo tono H=0.610, s=1.0, l subida de 0.649 a 0.674): 4.54:1 sobre surface-2 y sobre
sidebar-active (#272d3a), 6.27:1 sobre bg. Se usa en `.timeline-item-expand` y en cualquier
texto/icono que antes usara `color: var(--color-accent)`. `--color-accent` conserva #4c89ff
para usos no textuales (border, box-shadow, accent-color de form controls).
