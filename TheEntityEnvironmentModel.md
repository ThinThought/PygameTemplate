# The Entity-Environment-Interaction Model

Es un modelo que ahora mismo utiliza dos entidades basicas para
la construccion de un sistema para videojuegos: Environment y Entity.

Los principios son simples y parten de la programacion orientada a objetos:

## Environment o entorno
Representa espacios. 
Un entorno puede tener propiedades o declarar normas que se transmiten de manera directa a sus entidades hijas. 
 
- Existe el Environment Vacio, que no tiene ninguna regla que afecte a las entidades hijas.
- Un environment puede nacer por si mismo, o puede nacer como hijo de una entidad.
- Un environment puede sumar las caracteristicas de otros environment dentro de la entidad que habite.
- Los environments interactuan entre si sumando sus caracteristicas. La suma de propiedades de uno o mas environments se transmiten de manera individual a las entidades hijas de cada environment.


## Entity o entidad
Representa objetos interactivos dentro del entorno. Pueden ser personajes, items, obstaculos, etc.

La entidad puede ser dotada de cualquier tipo variable o componente que la habilite para interactuar con un entorno del cual es hija.

- La entidad siempre nace dentro de un Environment.
- La entidad puede tener estar dotada de environments, que permiten la creacion de otras entidades.