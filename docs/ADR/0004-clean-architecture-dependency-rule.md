# ADR-0004: Clean Architecture y regla de dependencias

- **Estado:** Aceptada
- **Fecha:** 2026-07-02
- **Fase:** 1

## Contexto

El proyecto debe ser de **largo plazo**, **extensible** (nuevos auriculares sin
 tocar el núcleo) y **seguro** (modificaciones reversibles sobre el sistema
 Linux). Estos requisitos exigen una arquitectura que aísle la lógica de negocio
 de los detalles técnicos mutables (BlueZ, PipeWire, Qt).

## Decisión

Adoptar **Clean Architecture** con cuatro capas y una **regla de dependencias
unidireccional**:

```
presentation → application → domain ← infrastructure
```

### Capas

| Capa | Responsabilidad | Depende de |
|------|-----------------|------------|
| `domain/` | Núcleo: modelos, enumeraciones, contratos (interfaces) | **Solo stdlib** |
| `application/` | Casos de uso que orquestan repositorios | `domain` |
| `infrastructure/` | Implementaciones concretas (BlueZ, PipeWire, etc.) | `domain` (implementa interfaces) + librerías externas |
| `presentation/` | UI (PySide6) y notificaciones | `application` |

### Invariante

- `domain` **no importa** nada de `infrastructure`, `application` ni
  `presentation`.
- `application` **no importa** nada de `infrastructure` ni `presentation`; recibe
  las implementaciones de interfaces por **inyección de dependencias**.
- `infrastructure` **no importa** `presentation`.

## Justificación (SOLID)

- **Dependency Inversion Principle (DIP):** las capas internas definen los
  contratos (`interfaces/`); las externas los implementan. La dirección de la
  dependencia apunta hacia el dominio.
- **Open/Closed Principle (OCP):** añadir un nuevo dispositivo o un nuevo
  backend de audio = añadir un perfil o una nueva implementación de interfaz, sin
  modificar el núcleo.
- **Single Responsibility Principle (SRP):** cada módulo tiene un motivo único
  de cambio.

## Consecuencias

- **Positivas:**
  - Testabilidad: el dominio y los casos de uso se prueban con mocks de
    interfaces, sin hardware ni servicios.
  - Extensibilidad: nuevos dispositivos y backends son aditivos.
  - Claridad: la lógica de negocio vive en un solo lugar, agnóstico al stack.
- **Negativas:**
  - Más archivos e indirección (interfaces + implementaciones) que un monolito.
  - Se requiere disciplina para mantener la regla de dependencias (el linter y
    los tests ayudan a enforcing).

## Aplicación en el código

- Los casos de uso (`application/*UseCase`) reciben interfaces (`IBluetoothRepository`,
  `IAudioRepository`, etc.) en su constructor.
- Las implementaciones (`infrastructure/bluez/bluez_repository.py`, etc.)
  heredan de las interfaces del dominio.
- La UI llama a casos de uso, nunca a repositorios directamente.
