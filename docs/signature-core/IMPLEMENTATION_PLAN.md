# Implementation Plan — Agent Signature Core

## Sprint 1 — Core DB + Tools
1. Crear migración `db/modules/signature/000001_signature_schema.sql`.
2. Agregar `tools/signature_tool.py` con:
   - `signature_status`
   - `signature_template_upsert`
   - `signature_request_create`
   - `signature_request_get`
   - `signature_event_record`
   - `signature_approval_hash_create`
3. Registrar toolset `signature` en `toolsets.py`.
4. Crear tests unitarios de toolset y hash determinístico.

## Sprint 2 — Sandbox integration
1. Extender páginas `/w/<token>` para que approve abra modal de firma.
2. Capturar typed/drawn signature en browser.
3. Enviar evento `approved` con `signature_text`, `signature_image_sha256`, `approval_context`.
4. Ingestar evento en Signature Core y crear approval hash.
5. Mostrar hash de aprobación y respuesta del agente en bitácora.

## Sprint 3 — PDF/document signing requests
1. Generar páginas `/sign/<slug>` para PDFs independientes.
2. Guardar attachments de firma en filesystem controlado.
3. Generar PDF final básico con firma visual.
4. Calcular `document_hash_sha256` y audit JSON/PDF.

## QA gates
- Unit tests: signature tool + toolset resolution.
- DB migration applies cleanly on `agent-postgres`.
- E2E quote approval requires signature and persists hash.
- Browser QA: no JS errors, approval modal works, hash visible.
- Security QA: token opaque, no secrets in public page, payload bounded, DB append-only events.

## Security notes
- V1 approval hash is evidence/audit, not a qualified legal digital signature.
- Store only token hashes.
- Do not expose Agent DB/secrets to sandbox static host.
- Event receiver remains narrow; ingest worker writes to DB.
