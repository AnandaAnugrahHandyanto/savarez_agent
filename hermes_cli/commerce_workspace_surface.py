"""Public customer commerce workspace surface for Sales Core.

The owner operates through the agent, but customers need a lightweight public URL
for quote/catalog/invoice review. These routes intentionally use opaque public
tokens rather than dashboard session auth and only expose the document tied to
that token.
"""
from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from hermes_cli import agent_core_sql as sql
from tools import sales_tool

router = APIRouter()


def _user() -> str:
    return sql.runtime_env().get("SALES_DB_RUNTIME_USER", "sales_runtime")


def _q(value: Any) -> str:
    return sql.quote_literal(value)


def _j(value: Any) -> str:
    return sql.quote_jsonb(value)


def _money(value: Any, currency: str = "USD") -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        amount = 0.0
    return f"{currency} {amount:,.2f}"


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _get_workspace(public_token: str) -> dict[str, Any]:
    workspace = sql.one(
        f"""
        SELECT *, expires_at IS NOT NULL AND expires_at < now() AS is_expired
        FROM sales.customer_workspaces
        WHERE public_token={_q(public_token)}
        """,
        user=_user(),
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if workspace.get("is_expired") or workspace.get("status") == "expired":
        raise HTTPException(status_code=410, detail="Workspace expired")
    return workspace


def _workspace_events(workspace_id: str) -> list[dict[str, Any]]:
    return sql.rows(
        f"""
        SELECT event_type, actor_type, actor_ref, comment, metadata, occurred_at
        FROM sales.customer_workspace_events
        WHERE workspace_id={_q(workspace_id)}
        ORDER BY occurred_at ASC, workspace_event_id ASC
        """,
        user=_user(),
    )


def _record_event(
    workspace_id: str,
    event_type: str,
    *,
    actor_type: str = "customer",
    actor_ref: str | None = None,
    comment: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return sql.statement_one(
        f"""
        INSERT INTO sales.customer_workspace_events (workspace_id, event_type, actor_type, actor_ref, comment, metadata, occurred_at)
        VALUES ({_q(workspace_id)}, {_q(event_type)}, {_q(actor_type)}, {_q(actor_ref)}, {_q(comment)}, {_j(metadata or {})}, now())
        RETURNING *
        """,
        user=_user(),
    )


def _set_workspace_status(workspace_id: str, status: str) -> dict[str, Any] | None:
    return sql.statement_one(
        f"""
        UPDATE sales.customer_workspaces SET status='{status}', updated_at=now()
        WHERE workspace_id={_q(workspace_id)}
        RETURNING *
        """,
        user=_user(),
    )


def _document_for_workspace(workspace: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    document_type = workspace.get("document_type")
    document_id = workspace.get("document_id")
    if document_type == "quote":
        document = sql.one(f"SELECT * FROM sales.quotes WHERE quote_id={_q(document_id)}", user=_user())
        items = sql.rows(
            f"SELECT * FROM sales.quote_items WHERE quote_id={_q(document_id)} ORDER BY quote_item_id ASC",
            user=_user(),
        )
    elif document_type == "invoice":
        document = sql.one(f"SELECT * FROM sales.invoices WHERE invoice_id={_q(document_id)}", user=_user())
        items = sql.rows(
            f"SELECT * FROM sales.invoice_items WHERE invoice_id={_q(document_id)} ORDER BY invoice_item_id ASC",
            user=_user(),
        )
    elif document_type == "catalog":
        document = {"title": "Catálogo", "currency": "USD", "total": None, "status": workspace.get("status")}
        items = sql.rows(
            "SELECT product_id, sku, name AS description, 1 AS quantity, unit_price, unit_price AS line_total, currency FROM sales.products WHERE status='active' ORDER BY name ASC",
            user=_user(),
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported document type")
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document, items


def _mark_opened(workspace: dict[str, Any]) -> None:
    if workspace.get("status") == "pending":
        _set_workspace_status(workspace["workspace_id"], "viewed")
    _record_event(
        workspace["workspace_id"],
        "opened",
        actor_type="customer",
        metadata={"document_type": workspace.get("document_type"), "document_id": workspace.get("document_id")},
    )


def _items_html(items: list[dict[str, Any]], currency: str) -> str:
    rows = []
    for item in items:
        description = item.get("description") or item.get("name") or item.get("product_id") or "Item"
        rows.append(
            "<tr>"
            f"<td>{_e(description)}</td>"
            f"<td>{_e(item.get('quantity') or 1)}</td>"
            f"<td>{_money(item.get('unit_price'), item.get('currency') or currency)}</td>"
            f"<td>{_money(item.get('line_total') or item.get('unit_price'), item.get('currency') or currency)}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='4'>Sin ítems registrados.</td></tr>"


def _events_html(events: list[dict[str, Any]]) -> str:
    if not events:
        return "<p class='muted'>Todavía no hay comentarios.</p>"
    parts = []
    for event in events:
        comment = event.get("comment")
        if not comment and event.get("event_type") not in {"commented", "approved", "rejected", "signed"}:
            continue
        parts.append(
            "<div class='event'>"
            f"<strong>{_e(event.get('event_type'))}</strong>"
            f"<p>{_e(comment or '')}</p>"
            "</div>"
        )
    return "".join(parts) or "<p class='muted'>Todavía no hay comentarios.</p>"


def render_workspace_html(public_token: str, banner: str | None = None) -> str:
    workspace = _get_workspace(public_token)
    document, items = _document_for_workspace(workspace)
    events = _workspace_events(workspace["workspace_id"])
    _mark_opened(workspace)

    document_type = str(workspace.get("document_type") or "")
    document_type_label = {"quote": "Cotización", "catalog": "Catálogo", "invoice": "Factura"}.get(
        document_type, "Documento"
    )
    title = document.get("title") or workspace.get("document_id")
    currency = document.get("currency") or "USD"
    total = document.get("total")
    action_buttons = ""
    if workspace.get("status") not in {"approved", "rejected", "paid", "cancelled"}:
        action_buttons = f"""
          <form method="post" action="/w/{_e(public_token)}/approve" class="inline-form">
            <input name="signature" placeholder="Nombre para aceptar / firmar" />
            <input name="actor_ref" placeholder="Email o teléfono" />
            <button class="primary" type="submit">Aprobar</button>
          </form>
          <form method="post" action="/w/{_e(public_token)}/reject" class="inline-form">
            <input name="comment" placeholder="Motivo opcional" />
            <button class="danger" type="submit">Rechazar</button>
          </form>
        """

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_e(document_type_label)} — {_e(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
    body {{ margin: 0; background: #f7f4ee; color: #161411; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 18px; }}
    .card {{ background: #fffdf8; border: 1px solid #e9dfce; border-radius: 24px; box-shadow: 0 24px 80px rgba(34, 25, 9, .10); padding: 28px; }}
    .eyebrow {{ color: #866b3f; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: 12px; }}
    h1 {{ font-size: clamp(32px, 7vw, 64px); line-height: .94; margin: 12px 0; letter-spacing: -.05em; }}
    .summary {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin: 24px 0; }}
    .pill {{ border: 1px solid #eadfce; border-radius: 18px; padding: 16px; background: #fbf6ed; }}
    table {{ width: 100%; border-collapse: collapse; margin: 22px 0; }}
    th, td {{ padding: 14px 10px; border-bottom: 1px solid #eee1cf; text-align: left; }}
    th {{ color: #70562e; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .actions, .comment-box {{ display: grid; gap: 12px; margin-top: 22px; }}
    .inline-form {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    input, textarea {{ border: 1px solid #d9c9ae; border-radius: 14px; padding: 12px 14px; font: inherit; background: white; min-width: 220px; }}
    textarea {{ min-height: 100px; width: min(100%, 640px); }}
    button {{ border: 0; border-radius: 999px; padding: 12px 18px; font-weight: 800; cursor: pointer; }}
    .primary {{ background: #111; color: white; }}
    .danger {{ background: #7b1d1d; color: white; }}
    .secondary {{ background: #efe5d5; color: #18130b; }}
    .banner {{ background: #e7f7df; border: 1px solid #b8dfaa; border-radius: 16px; padding: 14px 16px; margin-bottom: 18px; }}
    .muted {{ color: #72665a; }}
    .event {{ border-left: 3px solid #d6bd8c; padding-left: 12px; margin: 12px 0; }}
  </style>
</head>
<body>
  <main>
    {f'<div class="banner">{_e(banner)}</div>' if banner else ''}
    <section class="card">
      <div class="eyebrow">{_e(document_type_label)} para {_e(workspace.get('customer_name') or 'cliente')}</div>
      <h1>{_e(title)}</h1>
      <p class="muted">Revisa los detalles, deja comentarios o aprueba para que el agente continúe con la orden, factura y pago.</p>
      <div class="summary">
        <div class="pill"><strong>Estado</strong><br>{_e(workspace.get('status'))}</div>
        <div class="pill"><strong>Documento</strong><br>{_e(workspace.get('document_id'))}</div>
        <div class="pill"><strong>Total</strong><br>{_money(total, currency) if total is not None else 'Según selección'}</div>
      </div>
      <table>
        <thead><tr><th>Concepto</th><th>Cant.</th><th>Precio</th><th>Total</th></tr></thead>
        <tbody>{_items_html(items, currency)}</tbody>
      </table>
      <div class="actions">{action_buttons}</div>
      <div class="comment-box">
        <h2>Comentarios</h2>
        {_events_html(events)}
        <form method="post" action="/w/{_e(public_token)}/comment">
          <textarea name="comment" placeholder="Escribe una pregunta o comentario para el agente"></textarea><br><br>
          <input name="actor_ref" placeholder="Tu email o teléfono" />
          <button class="secondary" type="submit">Enviar comentario</button>
        </form>
      </div>
    </section>
  </main>
</body>
</html>"""


def comment_workspace(public_token: str, comment: str, actor_ref: str | None = None) -> dict[str, Any]:
    workspace = _get_workspace(public_token)
    clean_comment = (comment or "").strip()
    if not clean_comment:
        raise HTTPException(status_code=400, detail="Comment is required")
    _set_workspace_status(workspace["workspace_id"], "commented")
    event = _record_event(workspace["workspace_id"], "commented", actor_ref=actor_ref, comment=clean_comment)
    return {"ok": True, "event": event}


def reject_workspace(public_token: str, comment: str | None = None, actor_ref: str | None = None) -> dict[str, Any]:
    workspace = _get_workspace(public_token)
    _set_workspace_status(workspace["workspace_id"], "rejected")
    event = _record_event(workspace["workspace_id"], "rejected", actor_ref=actor_ref, comment=comment)
    return {"ok": True, "event": event}


def approve_workspace(public_token: str, actor_ref: str | None = None, signature: str | None = None) -> dict[str, Any]:
    workspace = _get_workspace(public_token)
    metadata: dict[str, Any] = {"signature": signature} if signature else {}
    result: dict[str, Any] = {"ok": True}

    if workspace.get("document_type") == "quote":
        order_payload = json.loads(sales_tool._handle_order_create({
            "quote_id": workspace["document_id"],
            "metadata": {"source": "customer_workspace", "workspace_id": workspace["workspace_id"]},
        }))
        if not order_payload.get("ok"):
            raise HTTPException(status_code=500, detail=order_payload.get("error") or "Order conversion failed")
        order_id = order_payload.get("order", {}).get("order_id")
        invoice_payload = json.loads(sales_tool._handle_invoice_create({
            "order_id": order_id,
            "metadata": {"source": "customer_workspace", "workspace_id": workspace["workspace_id"]},
        }))
        if not invoice_payload.get("ok"):
            raise HTTPException(status_code=500, detail=invoice_payload.get("error") or "Invoice conversion failed")
        invoice_id = invoice_payload.get("invoice", {}).get("invoice_id")
        metadata.update({"order_id": order_id, "invoice_id": invoice_id})
        result.update({"order_id": order_id, "invoice_id": invoice_id})
    elif workspace.get("document_type") == "invoice":
        metadata.update({"invoice_id": workspace["document_id"]})
    else:
        metadata.update({"document_id": workspace["document_id"]})

    _set_workspace_status(workspace["workspace_id"], "approved")
    _record_event(
        workspace["workspace_id"],
        "approved",
        actor_ref=actor_ref,
        comment=signature,
        metadata=metadata,
    )
    return result


async def _form_text(request: Request, field: str) -> str | None:
    form = await request.form()
    value = form.get(field)
    return str(value).strip() if value is not None and str(value).strip() else None


@router.get("/w/{public_token}", response_class=HTMLResponse)
async def workspace_page(public_token: str) -> HTMLResponse:
    return HTMLResponse(render_workspace_html(public_token))


@router.post("/w/{public_token}/comment", response_class=HTMLResponse)
async def workspace_comment(public_token: str, request: Request) -> HTMLResponse:
    comment = await _form_text(request, "comment")
    actor_ref = await _form_text(request, "actor_ref")
    comment_workspace(public_token, comment or "", actor_ref=actor_ref)
    return HTMLResponse(render_workspace_html(public_token, banner="Comentario enviado. El agente recibió tu mensaje."))


@router.post("/w/{public_token}/approve", response_class=HTMLResponse)
async def workspace_approve(public_token: str, request: Request) -> HTMLResponse:
    actor_ref = await _form_text(request, "actor_ref")
    signature = await _form_text(request, "signature")
    approve_workspace(public_token, actor_ref=actor_ref, signature=signature)
    return HTMLResponse(render_workspace_html(public_token, banner="Aprobado. El agente continuará con la orden, factura y pago."))


@router.post("/w/{public_token}/reject", response_class=HTMLResponse)
async def workspace_reject(public_token: str, request: Request) -> HTMLResponse:
    comment = await _form_text(request, "comment")
    actor_ref = await _form_text(request, "actor_ref")
    reject_workspace(public_token, comment=comment, actor_ref=actor_ref)
    return HTMLResponse(render_workspace_html(public_token, banner="Rechazado. El agente recibió la respuesta."))
