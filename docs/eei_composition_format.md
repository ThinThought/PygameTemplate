# Formato de composición EEI

Este formato describe cómo serializar una composición del modelo **Entity-Environment-Interaction** (EEI) que usa el editor. Está pensado para archivos `*.eei.json` ubicados en `game/configs/compositions/` o en cualquier carpeta de proyecto que se quiera versionar.

## Objetivos

- Persistir el árbol de `Environment` → `Entity` generado en el editor.
- Conservar configuraciones específicas de cada instancia (posición, radios, estados propios).
- Declarar interacciones explícitas entre nodos sin mezclar lógica con código Python.
- Mantener el formato legible y fácil de migrar entre versiones de la plantilla.

## Estructura general

```json
{
  "version": 1,
  "metadata": {
    "name": "Nombre legible",
    "description": "Notas opcionales",
    "tags": ["prototype", "boss-room"]
  },
  "scene": {
    "canvas": [1028, 720],
    "origin": [0, 0]
  },
  "nodes": [],
  "interactions": []
}
```

- `version`: entero para poder migrar esquemas en el futuro.
- `metadata`: bloque libre para identificar la composición.
- `scene`: datos globales del canvas/escena.
- `nodes`: lista lineal con todos los elementos (`Environment` o `Entity`).
- `interactions`: lista opcional de relaciones explícitas (activadores, envíos de eventos, etc.).

## Nodo (`nodes[]`)

Cada elemento del árbol es un objeto con las claves siguientes:

```json
{
  "id": "env-001",
  "kind": "environment",
  "type": "game.environments.BlackZone",
  "parent": null,
  "transform": {
    "position": [360, 240],
    "rotation": 0.0,
    "scale": [1.0, 1.0]
  },
  "state": {
    "dims": [200, 200]
  },
  "children": ["ent-eye-1", "ent-mouth-1"]
}
```

- `id`: identificador único en el archivo (se recomienda un prefijo `env-` o `ent-`).
- `kind`: `"environment"` o `"entity"`. Define qué clase de objeto se instanciará.
- `type`: ruta importable de la clase (ej. `game.entities.Eye`). Esto permite que el editor/editor CLI resuelva la factoría.
- `parent`: `null` para nodos que cuelgan del `Scene Root`. Para entidades, debe apuntar al `id` del environment padre. Para environments, puede apuntar a `null` o al `id` de una entidad (nunca a otro environment, siguiendo `core/core_model`).
- `transform`: bloque genérico. `position` es obligatorio; `rotation` y `scale` son opcionales y pueden omitirse si no aplican.
- `state`: diccionario libre con parámetros específicos del tipo (radio, timers, flags). Cada factory del editor decide qué entradas usa.
- `children`: lista derivada que facilita reconstruir el árbol sin ordenar por `parent`. Puede omitirse si se reconstruye en tiempo de carga, pero se recomienda mantenerla para depuración.

## Interacción (`interactions[]`)

Las interacciones describen cómo un nodo influye sobre otro sin necesidad de código embebido:

```json
{
  "id": "int-blink-mouth",
  "source": "ent-eye-1",
  "target": "ent-mouth-1",
  "kind": "event",
  "trigger": {
    "event": "blink.finished",
    "conditions": {
      "min_open_time": 0.1
    }
  },
  "effect": {
    "action": "toggle",
    "args": {"field": "talking"}
  }
}
```

- `source` y `target` hacen referencia a `id` de nodos válidos.
- `kind` es libre pero se sugieren valores como `event`, `physics`, `audio`, `custom`.
- `trigger` y `effect` son bloques genéricos para describir condicionales/acciones. Los sistemas runtime pueden interpretarlos a su manera (por ejemplo, traducirlos a eventos del juego o scripts).
- Nada impide crear interacciones de ambiente a ambiente o entidad a ambiente, siempre que los `id` existan.

## Ejemplo completo

```json
{
  "version": 1,
  "metadata": {
    "name": "demo-face",
    "description": "Ojo y boca dentro de una BlackZone",
    "tags": ["demo", "eei"]
  },
  "scene": {
    "canvas": [1028, 720],
    "origin": [0, 0]
  },
  "nodes": [
    {
      "id": "env-blackzone-1",
      "kind": "environment",
      "type": "game.environments.BlackZone",
      "parent": null,
      "transform": {"position": [360, 240]},
      "state": {"dims": [280, 220]},
      "children": ["ent-eye-1", "ent-mouth-1"]
    },
    {
      "id": "ent-eye-1",
      "kind": "entity",
      "type": "game.entities.Eye",
      "parent": "env-blackzone-1",
      "transform": {"position": [320, 220]},
      "state": {"blink_duration": 0.12}
    },
    {
      "id": "ent-mouth-1",
      "kind": "entity",
      "type": "game.entities.Mouth",
      "parent": "env-blackzone-1",
      "transform": {"position": [400, 280]},
      "state": {"open_speed": 8.0}
    }
  ],
  "interactions": [
    {
      "id": "int-eye-mouth",
      "source": "ent-eye-1",
      "target": "ent-mouth-1",
      "kind": "event",
      "trigger": {"event": "blink.started"},
      "effect": {"action": "set", "args": {"field": "talking", "value": true}}
    }
  ]
}
```

Este ejemplo respeta las reglas descritas en `game/core/core_model`: los environments solo cuelgan del root o de entidades y las entidades siempre pertenecen a un environment. También muestra cómo una interacción puede coordinar comportamientos sin duplicar lógica en Python.

