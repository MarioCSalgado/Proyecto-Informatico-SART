# SART · Sistema de diseño

> Azul noche y verde azulado: una sala de control tranquila, que avisa sin alarmar.

**Tema:** claro · **Implementación:** `web/src/App.scss` (tokens en `:root`) y `web/src/tema.ts` (tema de MUI con los
mismos valores). Si cambias un valor aquí, cámbialo allí, y al revés.

SART es una herramienta de trabajo para jefaturas de urgencia y el Subdirector asistencial: se abre el lunes para
saber cómo viene la semana. El diseño tiene que dejar ver en segundos **el nivel del centro, la cifra del
pronóstico y qué hacer**, y nada más debe competir con eso. Por eso:

- **Una superficie oscura de marca** (azul noche) para lo más importante: el encabezado, la portada del inicio de
  sesión y el bloque del pronóstico de la semana.
- **Profundidad con superficies, no con sombras:** fondo de la aplicación → tarjeta blanca → lavado suave → bloque
  azul noche. Sin sombras apiladas ni brillos.
- **Lavados suaves (fríos) para separar zonas**, siempre derivados del azul o del verde azulado. Los cálidos
  (amarillo, naranjo, rojo) **quedan reservados para los niveles**: en un sistema de alertas, el color de una
  alerta no puede aparecer como decoración.
- **Formas suaves:** tarjetas de 16 px, bloques internos de 12 px, botones y etiquetas en píldora.
- **Dos familias, una voz:** Figtree en títulos y cifras; Noto Sans en el texto (la pareja «Medical Clean» de la
  skill ui-ux-pro-max, pensada para salud y accesibilidad).

Las ideas de superficies planas, lavados por zona y formas redondeadas se tomaron de una guía de estilo de
referencia; los colores, los componentes y la identidad son de SART.

## Colores

### Marca

| Nombre | Valor | Token | Uso |
|---|---|---|---|
| Azul noche | `#1b3352` | `--azul-noche` | Superficie oscura de marca: encabezado, portada del acceso, bloque del pronóstico. Títulos sobre claro (`--texto-titulo` es su variante) |
| Azul noche claro | `#2a4566` | `--azul-noche-claro` | Elementos sobre el azul noche: cuadro del logo, píldora de la sección activa, separadores |
| Azul noche profundo | `#13263f` | `--azul-noche-profundo` | Pie de la portada y fondos bajo el azul noche (solo como superficie) |
| Verde azulado | `#417f88` | `--teal` | **Acción principal** (botón lleno), foco de campos, serie del pronóstico en gráficos. Con texto blanco: 4,55:1 (AA) |
| Verde azulado oscuro | `#336a72` | `--teal-oscuro` | Botón principal al pasar el cursor o presionado |
| Verde azulado texto | `#2f7480` | `--teal-texto` | Enlaces, antetítulos e íconos sobre fondos claros (5,3:1 sobre blanco) |
| Verde azulado claro | `#8fc6cd` | `--teal-claro` | Acentos sobre azul noche (línea del gráfico de portada, anillo de foco) |

### Lavados (superficies suaves, siempre fríos)

| Nombre | Valor | Token | Uso |
|---|---|---|---|
| Fondo de la aplicación | `#edf2f2` | `--fondo-app` | Lienzo de todas las pantallas con sesión |
| Fondo del acceso | `#f3f5f6` | `--fondo-acceso` | Lado del formulario del inicio de sesión |
| Lavado verde azulado | `#e3eff0` | `--lavado-teal` | Tarjetas de apoyo (dotación sugerida), avisos informativos, círculo de los estados vacíos |
| Lavado azul | `#e7edf4` | `--lavado-azul` | Indicadores neutros (total de centros), barra de filtros, filas destacadas |
| Lavado niebla | `#f4f7f8` | `--superficie-suave` | Encabezados de tabla, campos deshabilitados, bloques «pendiente» |
| Blanco | `#ffffff` | `--superficie` | Tarjetas, campos, menús |

### Texto y bordes

| Nombre | Valor | Token | Uso |
|---|---|---|---|
| Título | `#1b2e45` | `--texto-titulo` | Títulos y cifras sobre claro |
| Texto | `#283746` | `--texto` | Texto corrido |
| Texto medio | `#556677` | `--texto-medio` | Bajadas y etiquetas (5,8:1 sobre blanco) |
| Texto suave | `#687584` | `--texto-suave` | Notas y datos de apoyo sobre blanco (4,7:1). Sobre el fondo de la aplicación o un lavado, usar `--texto-medio` |
| Borde | `#d9e1e3` | `--borde` | Separadores y contorno de tarjetas blancas |
| Borde fuerte | `#c3ced2` | `--borde-fuerte` | Contorno de campos y botones secundarios |

### Niveles (reservados: solo para el nivel de un centro o del aire)

El nivel **nunca se muestra solo con color** (RNF-U-1): siempre va con su texto y con un ícono de forma distinta
(círculo con visto, círculo con signo de exclamación, triángulo), legible también en blanco y negro.

| Nivel | Texto | Fondo | Borde | Ícono |
|---|---|---|---|---|
| Normal | `#1d6b45` | `#e1f0e8` | `#b7dbc6` | círculo con visto |
| Atención | `#7c5a00` | `#fcf1c4` | `#ead48a` | círculo con «!» |
| ALERTA | `#ad430c` | `#fdeee3` | `#f1c7a8` | triángulo con «!» |
| Error del sistema | `#a3261d` | `#fdecea` | — | — |

Escala de MP2,5 (RB-1): normal `#1d6b45`, sobre la norma `#7c5a00`, alerta `#ad430c`, preemergencia `#a3261d`,
emergencia `#6b2c91`. Todos cumplen 4,5:1 sobre blanco.

## Tipografía

- **Figtree** (600, 700) para títulos, cifras e indicadores. · `--fuente-titulos`
- **Noto Sans** (400, 500, 600, 700) para todo lo demás. · `--fuente-texto`
- Cifras con `font-variant-numeric: tabular-nums` en tablas, indicadores y rangos.
- Nunca texto corrido bajo 14 px; 12 px solo para etiquetas en mayúsculas.

| Rol | Familia | Peso | Tamaño | Interlínea | Espaciado | Token |
|---|---|---|---|---|---|---|
| Etiqueta (antetítulo, encabezado de tabla) | Noto Sans | 700, mayúsculas | 12–13 px | 1,3 | 0,06 em | `--texto-etiqueta` |
| Pequeño | Noto Sans | 400 | 14 px | 1,45 | normal | `--texto-pequeno` |
| Texto | Noto Sans | 400 | 16 px | 1,5 | normal | `--texto-base` |
| Destacado | Noto Sans | 400 | 18 px | 1,5 | normal | `--texto-destacado` |
| Título de bloque (h3) | Figtree | 600 | 18–20 px | 1,3 | -0,005 em | `--titulo-3` |
| Título de tarjeta (h2) | Figtree | 700 | 22–24 px | 1,25 | -0,01 em | `--titulo-2` |
| Título de página (h1) | Figtree | 700 | 34 px (28 en celular) | 1,15 | -0,015 em | `--titulo-1` |
| Cifra (indicadores) | Figtree | 700 | 32–36 px | 1 | -0,02 em | `--cifra` |
| Cifra principal (pronóstico) | Figtree | 700 | 56 px (44 en celular) | 1 | -0,025 em | `--cifra-grande` |
| Lema del acceso | Figtree | 600 | hasta 56 px | 1,1 | -0,02 em | — |

## Espacios, formas y movimiento

- **Unidad:** 4 px. Escala: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- **Página:** ancho máximo 1280 px, margen lateral 48 px (16 px en celular), 28 px entre bloques.
- **Tarjeta:** relleno 28 × 32 px (20 × 18 px en celular).

| Elemento | Radio | Token |
|---|---|---|
| Botones, etiquetas, píldoras de nivel, pestañas | 999 px (píldora) | `--radio-pildora` |
| Tarjetas y bloque del pronóstico | 16 px | `--radio-tarjeta` |
| Bloques internos, campos, avisos | 12 px | `--radio-bloque` |
| Cuadros de íconos, celdas del calendario | 8 px | `--radio` |

- **Sombras:** ninguna para dar altura. Solo el anillo de foco (`3px` de `--teal-claro` o `0 0 0 3px` del teal al
  18 %) y una sombra mínima para menús flotantes (`0 8px 24px rgba(27, 51, 82, 0.12)`).
- **Movimiento:** 150–200 ms con `ease-out` en color, fondo y borde. Nada se anima en ancho ni alto. Con
  `prefers-reduced-motion: reduce`, sin transiciones ni el brillo de carga.

## Componentes

### Botón principal
Verde azulado `#417f88`, texto blanco Noto Sans 600 a 16 px, alto mínimo 48 px, relleno 0 24 px, **píldora**. Al
pasar el cursor, `#336a72`. Uno solo por zona: es la acción que se espera.

### Botón secundario
Fondo blanco, borde 1 px `--borde-fuerte`, texto `--texto-titulo` 600, alto mínimo 44 px, píldora. Al pasar el
cursor, borde y texto en verde azulado y fondo `--lavado-teal`.

### Encabezado
Azul noche a todo el ancho, 76 px de alto. Logo a la izquierda; secciones al centro; iniciales en un círculo
`--azul-noche-claro`, nombre, rol y «salir» a la derecha. **La sección activa es una píldora `--azul-noche-claro`
con texto blanco**; las demás, texto blanco al 72 %.

### Cabecera de página
Antetítulo como etiqueta en píldora (`--lavado-teal`, texto `--teal-texto`), título h1 en Figtree 34 px, bajada en
texto destacado `--texto-medio`. Acciones de la página a la derecha.

### Tarjeta
Blanco, borde 1 px `--borde`, radio 16 px, relleno 28 × 32 px. Título h2 Figtree; bajada 14–15 px en
`--texto-medio`.

### Tarjeta suave
Igual que la tarjeta, pero con fondo de lavado (`--lavado-teal` o `--lavado-azul`) y sin borde. Para información de
apoyo, como la dotación sugerida.

### Bloque del pronóstico
La pieza principal de «Mi centro». Fondo azul noche, texto blanco, radio 16 px. Antetítulo en `--teal-claro`, la
cifra del pronóstico en Figtree 56 px, el intervalo de 90 % debajo y la insignia del nivel. El gráfico va al lado,
sobre una superficie blanca con radio 12 px, para que no compita con la cifra.

### Insignia de nivel
Píldora con el fondo y el texto del nivel, borde 1 px del nivel, ícono SVG de 18 px y texto 600. En las tablas, la
versión corta (cuadro de 8 px de radio con la abreviatura y su nombre completo en `title`).

### Indicador (resumen de la red)
Tarjeta con ícono en un cuadro de 40 px y radio 10 px, cifra Figtree 36 px y etiqueta debajo. El total va sobre
`--lavado-azul`; los de nivel, en tarjeta blanca con el ícono del nivel sobre su fondo y la etiqueta en el color
del nivel. No se tiñe la tarjeta completa: un bloque amarillo o naranjo grande grita aunque el conteo sea cero.

### Campo
Etiqueta 600 en `--texto-titulo` arriba (nunca solo el texto de ejemplo), caja de 52 px de alto, borde 1 px
`--borde-fuerte`, radio 12 px. Foco: borde verde azulado y anillo `0 0 0 3px rgba(65, 127, 136, 0.18)`. Error: texto
y borde `--error-texto` junto al campo.

### Pestañas
Control segmentado: una píldora `--superficie-suave` que contiene las pestañas; la activa, blanca con texto
`--texto-titulo` y borde `--borde`. Alto mínimo 44 px.

### Estado vacío
Ícono de 30 px en un círculo `--lavado-teal` de 64 px, título Figtree 18 px y una frase que explica qué va a
aparecer y cuándo.

### Aviso
Bloque de radio 12 px con ícono a la izquierda. Informativo en `--lavado-teal`; error en `--error-fondo` con una
franja de 4 px `--error-texto`. Los avisos de nivel usan los colores del nivel y su ícono.

### Tabla
Encabezado en `--superficie-suave` con etiquetas en mayúsculas de 12–13 px; filas de 52 px con separador 1 px
`--borde`; cifras tabulares alineadas a la derecha. En pantallas angostas, desplazamiento horizontal propio de la
tabla (nunca de la página).

### Gráfico de consultas
Observado: línea continua azul noche de 3 px. Pronóstico: línea discontinua verde azulado. Intervalo de 90 %: banda
verde azulado al 18 %. Umbral de alerta: línea fina `#ad430c` con su rótulo. Leyenda siempre visible y tabla
alternativa («Ver como tabla»); la forma de la línea distingue las series, no solo el color.

## Sí y no

### Sí
- Usar el azul noche para lo más importante de cada pantalla, y una sola vez.
- Mostrar el nivel con texto **e** ícono, siempre.
- Separar zonas con lavados fríos y espacio, no con líneas ni sombras.
- Usar Figtree para títulos y cifras, Noto Sans para el texto.
- Mantener 44 px como área mínima de cualquier control.

### No
- No usar amarillo, naranjo ni rojo fuera de los niveles y los errores (ni en botones, ni en fondos, ni en íconos
  decorativos).
- No agregar sombras para dar altura ni degradados de fondo (salvo el brillo de carga).
- No usar bordes rectos (0–4 px) en tarjetas ni botones.
- No poner texto `--texto-suave` sobre un lavado: sobre lavados, usar `--texto-medio` o más oscuro.
- No usar emojis ni caracteres sueltos como íconos: íconos SVG de `@mui/icons-material`, con `aria-hidden` cuando
  acompañan un texto.

## Fuentes

```html
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@600;700&family=Noto+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
```

## Tokens (CSS)

```css
:root {
  /* Marca */
  --azul-noche: #1b3352;
  --azul-noche-claro: #2a4566;
  --azul-noche-profundo: #13263f;
  --teal: #417f88;
  --teal-oscuro: #336a72;
  --teal-texto: #2f7480;
  --teal-claro: #8fc6cd;

  /* Lavados y superficies */
  --fondo-app: #edf2f2;
  --fondo-acceso: #f3f5f6;
  --lavado-teal: #e3eff0;
  --lavado-azul: #e7edf4;
  --superficie: #ffffff;
  --superficie-suave: #f4f7f8;

  /* Texto y bordes */
  --texto-titulo: #1b2e45;
  --texto: #283746;
  --texto-medio: #556677;
  --texto-suave: #687584;
  --borde: #d9e1e3;
  --borde-fuerte: #c3ced2;

  /* Niveles (RNF-U-1) */
  --normal-texto: #1d6b45;   --normal-fondo: #e1f0e8;   --normal-borde: #b7dbc6;
  --atencion-texto: #7c5a00; --atencion-fondo: #fcf1c4; --atencion-borde: #ead48a;
  --alerta-texto: #ad430c;   --alerta-fondo: #fdeee3;   --alerta-borde: #f1c7a8;
  --error-texto: #a3261d;    --error-fondo: #fdecea;

  /* Tipografía */
  --fuente-titulos: "Figtree", "Noto Sans", "Segoe UI", sans-serif;
  --fuente-texto: "Noto Sans", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;

  /* Formas */
  --radio: 8px;
  --radio-bloque: 12px;
  --radio-tarjeta: 16px;
  --radio-pildora: 999px;
  --trans: 0.18s ease-out;
}
```
