# Pygame Videogame Maker

Un creador de juegos de plataformas 2D con un editor visual, construido con Pygame.

Este proyecto te permite diseñar y construir niveles utilizando un editor incorporado y luego jugar inmediatamente.

[SCREENSHOT: Gameplay mostrando al personaje jugador, plataformas y el fondo.]

## Características

*   **Editor Visual**: Crea y modifica niveles en tiempo real. Coloca plataformas, enemigos y otros elementos del juego visualmente.
*   **Modelo Entidad-Entorno (EEI)**: Una arquitectura flexible para definir objetos del juego y sus interacciones.
*   **Soporte para Mandos**: Perfiles de mando configurables para una experiencia de juego plug-and-play.
*   **Listo para Despliegue**: Incluye scripts para empaquetar y desplegar el juego en consolas retro compatibles.

## Primeros Pasos

### 1. Instalación

Para instalar las dependencias del proyecto, ejecuta el siguiente comando:

```bash
uv sync
```

### 2. Ejecutar el Editor

El proyecto incluye un editor visual que se ejecuta por defecto. Para lanzarlo, usa este comando:

```bash
uv run pygame-editor
```

Esto abrirá la ventana principal, cargando la escena del editor.

### 3. Jugar al Juego

Dentro de la aplicación, puedes cambiar entre diferentes escenas (Editor, Juego, Test de Input) usando las siguientes teclas:

*   **F2 / Tab**: Cambiar a la siguiente escena.
*   **F1 / Shift+Tab**: Cambiar a la escena anterior.

La escena principal del juego (`MainScene`) es típicamente la primera en el ciclo, permitiéndote jugar los niveles que has creado.

## El Editor Visual

El editor es la herramienta central para construir tu juego. Te permite:

*   **Componer Escenas**: Añade, selecciona y mueve entidades directamente en el espacio del juego.
*   **Configurar Propiedades**: Ajusta las propiedades de cada entidad, como su sprite, comportamiento y atributos físicos.
*   **Exportar Niveles**: Guarda tus creaciones en un archivo de composición (`.eei.json`) que el juego puede cargar.

[SCREENSHOT: La interfaz del editor visual, mostrando la colocación de entidades y el editor de propiedades.]

## El Modelo Entidad-Entorno (EEI)

El proyecto utiliza un modelo de diseño donde el juego se construye a partir de dos componentes principales:

*   **Entornos (`Environment`)**: Representan espacios o zonas que aplican reglas a los objetos dentro de ellos. Por ejemplo, un entorno de "gravedad" aplica una fuerza hacia abajo a todas las entidades que contiene. Los entornos se pueden anidar y sus efectos se combinan.
*   **Entidades (`Entity`)**: Son los objetos interactivos del juego, como el jugador, los enemigos, las plataformas o los ítems. Las entidades viven dentro de los entornos y son afectadas por sus reglas.

Este modelo permite una forma flexible y componible de construir lógicas de juego complejas.

puedes ajustar la resolución de la pantalla, los FPS y otros ajustes generales en `game/configs/settings.toml`.

```toml
title = "Pygame Videogame Maker"
width = 1280
height = 720
fps = 60
```

### Controles y Mandos

Los mapeos de los mandos se definen en `game/configs/controllers/generic.toml`. Puedes editar este archivo para adaptar el juego a diferentes gamepads sin cambiar el código.

```toml
# Ejemplo de mapeo de un botón
a = { type = "button", index = 0, label = "A" }
```

## Despliegue en Consola

Si estás trabajando con una consola retro o un dispositivo similar, puedes usar el script de despliegue para empaquetar y transferir tu juego:

```bash
bash deploy_to_console.sh
```

El script se encarga de empaquetar las dependencias y los assets necesarios.

## Scripts de Utilidad

### Optimizar Imágenes PNG

El proyecto incluye un script para recortar el espacio transparente sobrante en tus sprites, optimizando su tamaño en memoria.

```bash
# Recorta todas las imágenes en la carpeta de plataformas
uv run python scripts/prune_pngs.py game/assets/images/platforms/grass_platforms
```
