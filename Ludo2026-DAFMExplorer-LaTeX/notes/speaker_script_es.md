# Guion del orador (español) — ~20 minutos

**Charla:** Exploring the Sonic Universe of the Sega Genesis  
**Evento:** Ludo2026, Session 9 — *Synthesis, Served Three Ways*  
**Presenta:** Abraham Casas (Maria Cerro en autoría; Abraham habla todo)  
**Slides:** inglés · **Este guion:** español  
**Léxico:** *extracción de datos* / *análisis exploratorio (EDA)* — no “notebook 01/02”

Duración objetivo: **20 min** + preguntas. Los bloques llevan timing orientativo.

---

## 0:00–2:00 — Portada y quiénes somos

Buenos días. Somos **Abraham Casas** y **Maria Cerro**, de **Kasser Synths**. Yo presento hoy.

Kasser Synths es un estudio pequeño que trabaja con chips Yamaha de síntesis FM y con el legado sonoro de los juegos de los 80 y 90. **DAFMExplorer** es la parte abierta de ese trabajo: tratar los presets del Mega Drive / Genesis como un corpus que se puede medir… y volver a escuchar.

*(Slide fotos: sustituir placeholders cuando tengáis retratos.)*

---

## 2:00–5:00 — La voz de una plataforma también son sus presets

Cuando pensamos en la música del Genesis, pensamos en melodías y temas. Pero debajo hay otra capa: **timbres programados** — presets FM — que se reutilizan, se mezclan con el SFX y se escriben bajo las reglas de un solo chip, el **YM2612**.

Breve arco: **Chowning** → **DX7** → **YM2612** (4 ops, 8 algoritmos).

### Kit de escucha en vivo

Cuatro momentos cortos a lo largo de la charla (VGM → preset):

| # | Juego | Qué oír |
|---|-------|---------|
| L1 | *Streets of Rage* | energía Koshiro → preset FL alto |
| L2 | *Pulseman* | marca Alg. 5 → preset CON=5 |
| L3 | *Nightmare Circus* | GEMS → voz de herramienta |
| L4 | *Thunder Force IV* | driver custom → otro CON |

Archivos VGM offline + DAFMExplorer; detalle en `videos/LIVE_DEMOS.md`.

---

## 5:00–8:00 — Extracción de datos: hacer hablar al archivo

*(▶ VIDEO 1 — OPM → fila con metadatos)*

El archivo ya existía: grabaciones **VGM**, proyectos como **Project2612** / **VGMrips**, y la colección **DrWashington** con presets en formato **OPM**. Más de **93.000** voces. Lo que faltaba en ludomusicología era tratarlas como **datos estructurados**.

La **extracción** hace el trabajo poco glamuroso pero decisivo:

1. Parsear cada preset (~58 parámetros).
2. Deduplicar por timbre: el parámetro **TL** a menudo solo cambia el volumen de mezcla; el mismo instrumento aparece muchas veces.
3. Normalizar nombres de juego (títulos regionales, alias).
4. Enriquecer: compositor, nacionalidad, uso de **GEMS**.

Sin ese paso, el análisis solo mediría ruido de archivo.

### Por qué el TL rompe el conteo ingenuo

Misma arquitectura FM y mismas envolventes, distinto TL = mismo instrumento a otro nivel de mezcla. Si contáramos cada fila, inventaríamos miles de “instrumentos falsos”. Deduplicar sobre parámetros que no son TL conserva **una** decisión creativa.

---

## 8:00–13:00 — Técnica FM + EDA de parámetros

Un preset no es magia: canal (**algoritmo CON**, **feedback FL**, …) y **cuatro operadores** (envolventes, TL, MUL…). Los *carriers* son lo que oyes; los *modulators* dibujan el espectro.

### Algoritmos como cableado

Antes del histograma: tres esquemas (Alg. 4 / 5 / 2). Mismos cuatro operadores; distinto CON = distinta arquitectura de instrumento.

### Algoritmo 4 como caballo de batalla (corpus)

El histograma de **CON** muestra que el **algoritmo 4** domina a escala global: dos voces FM sumadas — flexible y fácil de mezclar.

### Fingerprints de juego: compromiso vs variedad

- **Pulseman**: un algoritmo domina (aquí Alg. 5) — marca sónica por compromiso.
- **Thunder Force IV**: reparte CON — identidad por variedad.

*(▶ LIVE L2 — VGM Pulseman → preset CON=5 en DAFMExplorer)*

### Feedback como estética binaria

*(▶ VIDEO 2 — oír FL 0 vs FL 7)*

El **feedback** casi no tiene términos medios: **0 o 7**. Interruptor estilístico, no potenciómetro fino.

### Un “sweet spot” de brillo

Índice de **brightness**: masa en valores medio-altos (TV pequeña, mix denso). Algunos títulos brillan más; otros se quedan deliberadamente oscuros.

---

## 13:00–17:30 — GEMS, región, compositores

### GEMS

**GEMS** fue la herramienta oficial de Sega of America a mediados de los 90. En el corpus es una **variable de herramienta**.

### GEMS en la práctica

Contraste concreto: **Nightmare Circus** (GEMS) frente a **Thunder Force IV** (no GEMS).

*(▶ LIVE L3+L4 — VGM + preset de cada uno; distinto “barrio” de algoritmo)*

### Región y herramienta

Japón / USA / UK como **hipótesis** sobre práctica.

### Firmas de compositor

*(▶ LIVE L1 — preferido; VIDEO 3 solo si falla el directo)*

- **Yuzo Koshiro** — house/techno en el YM2612 (*Streets of Rage*).
- **Masato Nakamura** — pop en *Sonic* (contexto histórico; el metadato del corpus a veces falla en atribuciones).

VGM de *Streets of Rage* → preset FL alto del mismo juego.

### Más firmas: Kodaka y Uematsu

- **Naoki Kodaka**: el CON modal se aparta del default Alg. 4 — routing más idiosincrático.
- **Nobuo Uematsu**: cerca de la gramática compartida, con su propia paleta.

Convergencia en el chip ≠ personalidades idénticas.

---

## 17:30–20:00 — Zoom out, límites, cierre

A escala completa, los presets forman **barrios tímbricos**. Siete “reinos sónicos” emergentes como **lectura del corpus**, no taxonomía impuesta.

### Lo que el dato no dice

Un preset no es la partitura completa; el archivo tiene sesgos; los mapas son exploratorios; “estilo nacional” y “sonido GEMS” son hipótesis. El premio: mejores preguntas sobre la práctica de plataforma — con sonidos que aún se pueden oír.

*(Demo app opcional ≤60 s — si Wi‑Fi falla, saltar.)*

Método abierto. **DAFMExplorer**: https://dafm-explorer.vercel.app/

Gracias. Preguntas bienvenidas.

---

## Cues rápidos de vídeo / live

| Min (aprox.) | Cue | Contenido |
|--------------|-----|-----------|
| ~6–7 | VIDEO 1 | Extracción: OPM → metadatos |
| ~11 | LIVE L2 | Pulseman VGM → preset Alg. 5 |
| ~12 | VIDEO 2 | Feedback 0 vs 7 (o extremos) |
| ~14 | LIVE L3+L4 | Nightmare Circus vs Thunder Force IV |
| ~15–16 | LIVE L1 | Streets of Rage VGM → preset Koshiro |
| ~17 | App (opc.) | Mapa + play, ≤60 s |

## Notas anti-jerga

- Decir “mapa donde vecinos suenan parecido”, no “UMAP”.
- Decir “agrupaciones emergentes”, no “KMeans con k=7 por elbow”.
- Decir “extracción” y “análisis exploratorio”, no “notebook uno / dos”.
