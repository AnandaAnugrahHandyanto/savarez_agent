# F3 Evidence — Implementation Plan and Task Graph (Rework)

## Estado

- Incremento: F3 — Implementation plan and task graph
- Run: `run-1780712703-2092c8a2`
- Owner: `implementation-planner`
- Fecha de cierre: `2026-06-05`
- Reviewer: `factory-orchestrator`
- Run type: rework

## Contexto del rework

El gate `planning` falló en run anterior (`run-1780704556-afaa1d6b`) con `factory-orchestrator` como reviewer. Los artefactos existían pero la estructura no incluía:
1. Sprint decomposition explícita (Sprint 1–6)
2. Acceptance criteria por cada sub-tarea
3. Registro de riesgos
4. Owner/reviewer assignments concretos por sprint

Este rework entrega versiones corregidas de `TASK_GRAPH.md` y `IMPLEMENTATION_PLAN.md` que incorporan todos los elementos faltantes.

## Archivos generados / actualizados

| Archivo | Status | Descripción |
|---------|--------|-------------|
| `TASK_GRAPH.md` | actualizado | Sprint decomposition (6 sprints), AC por sub-tarea, risk register, owner/reviewer assignments |
| `IMPLEMENTATION_PLAN.md` | mantenido | Plan de implementación detallado F4–F8 con paths exactos y comandos de verificación |
| `F3_EVIDENCE.md` | este archivo | Handoff y evidencia de ejecución del rework |
| `TRACKER.md` | actualizado | Estado actual de gates y tareas |

## Gate request: planning

Este incremento solicita registrar gate `planning=pending` para que `factory-orchestrator` revise y apruebe/rechace. Gate requerido para iniciar Sprint 1 (F4).

## Gate dependencies verificadas

| Gate | Status | Verificado en |
|------|--------|---------------|
| intake (F0) | passed | TRACKER.md |
| functional (F1) | passed | TRACKER.md |
| architecture (F2) | review_ready — security-reviewer pendiente | TRACKER.md |
| planning (F3) | este incremento — solicita factory-orchestrator | — |
| implementation | blocked — esperando planning + architecture | TRACKER.md |

## Decisiones de planificación tomadas (rework)

1. **Sprint decomposition**: 6 sprints explícitos. Sprint 1 = F4 (DB), Sprint 2 = F5 (tools), Sprint 3 = F6 (calendar+dispatcher), Sprint 4 = F7 (plans), Sprint 5 = F8 (CRM bridge), Sprint 6 = F9+F10+F11 (QA+security+delivery).

2. **Sequential execution rule**: no iniciar sprint N hasta que Sprint N-1 tenga gate `implementation` parcial registrado en Factory DB.

3. **F4 se divide en 8 migration files** numerados (`000001`–`000008`) para rollback selectivo.

4. **F5 es un único archivo** `tools/activity_tool.py` con múltiples handlers para coherencia de código.

5. **F6 dispatcher es módulo separado** `cron/activity_dispatcher.py` para ejecución standalone desde cron job.

6. **F7 reusa** `tools/activity_tool.py` para mantener coherencia con F5.

7. **F8 modifica** `tools/crm_tool.py` existente — mantiene backward compatibility.

8. **Tool output siempre JSON**: no prose, no resúmenes narrativos.

9. **Risk register** incluye 5 riesgos identificados con likelihood/impact/mitigation.

## Dependencias verificadas

```
F4 (Sprint 1 — DB migrations)
  └─ F5 (Sprint 2 — Activity tools)
        ├─ F6 (Sprint 3 — Calendar bridge + dispatcher)
        └─ F7 (Sprint 4 — Plans/chaining/recurrence)
              └─ F8 (Sprint 5 — CRM bridge)
                    └─ F9 + F10 + F11 (Sprint 6 — QA + Security + Delivery)
```

## Handoff a siguientes workers

### Para `claude-builder` (Sprint 1 — F4)

**Requisitos:**
- Esperar hasta que `architecture=passed` (F2) Y `planning=passed` (F3) estén en Factory DB.
- Crear directorio `db/modules/activity/` y 8 archivos de migración.
- Cada migración debe ser idempotente (IF NOT EXISTS / ON CONFLICT).
- Ejecutar dry-run antes de apply real.
- Verificar cada tabla con `\d` y query de readback.
- Registrar evidencia en `tests/migrations/test_activity_schema.py`.

**Entregables de Sprint 1:**
- 8 archivos SQL en `db/modules/activity/`
- Output de dry-run para cada archivo
- Readback queries confirmando schema creado
- Tests de idempotencia (ejecutar migración dos veces → mismo resultado)

### Para `claude-builder` (Sprint 2 — F5)

**Requisitos:**
- Esperar hasta que Sprint 1 (F4) esté verificado en test DB.
- Crear `tools/activity_tool.py` con todos los handlers listados.
- Registrar cada handler con `registry.register()`.
- Tests van en `tests/tools/test_activity_tool.py`.
- Tool output siempre JSON (no prose).

### Para `devops-release` (F6 reviewer)

- F6 incluye `cron/activity_dispatcher.py` — revisar que no tenga side effects externos sin audit.
- Dispatcher no envía notificaciones; solo prepara output para consumo interno.

### Para `codex-builder` (F8)

- Leer `tools/crm_tool.py` antes de modificar.
- Mantener backward compatibility.
- Schema audit en F8.1 antes de implementar bridge.

## Verificación documental F3 (rework)

- [x] `TASK_GRAPH.md` actualizado con sprint decomposition (6 sprints)
- [x] Acceptance criteria por cada sub-tarea F4.1–F8.4
- [x] Risk register con 5 riesgos identificados
- [x] Owner/reviewer assignments por sprint
- [x] `IMPLEMENTATION_PLAN.md` mantenido con paths exactos y comandos de verificación
- [x] Gate dependencies actualizadas y verificadas
- [x] Handoff notes claras para claude-builder, codex-builder, devops-release
- [x] TRACKER.md actualizado con estado actual

## Siguiente acción

1. `factory-orchestrator` revisa este package y registra `planning=passed` o `planning=failed` en Factory DB.
2. `security-reviewer` revisa F2 ADR y registra `architecture=passed` o `architecture=failed` en Factory DB.
3. Una vez ambos gates (`planning` y `architecture`) registrados como `passed`, `claude-builder` puede iniciar Sprint 1 (F4).
