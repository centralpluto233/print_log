"""REST API used by the Print Log panel. Reads need a login, writes need an admin."""
from __future__ import annotations

import sqlite3
from functools import partial

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import PrintLogData
from .exports import settlement_csv, settlement_html

TABLES = ("people", "roles", "filaments", "printers")


def _is_admin(request: web.Request) -> bool:
    user = request.get("hass_user")
    return bool(user and user.is_admin)


def _err(status: int, msg: str) -> web.Response:
    return web.json_response({"error": msg}, status=status)


class _Base(HomeAssistantView):
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    @property
    def data(self) -> PrintLogData:
        return self.hass.data[DOMAIN]["_current"]

    async def _run(self, func, *args, **kwargs):
        return await self.hass.async_add_executor_job(partial(func, *args, **kwargs))

    async def _write(self, request: web.Request, func, *args, _reload: bool = False):
        if not _is_admin(request):
            return _err(403, "admin required")
        try:
            result = await self._run(func, *args)
        except (ValueError, TypeError) as e:
            return _err(400, str(e))
        except sqlite3.IntegrityError as e:
            return _err(409, f"conflict: {e}")
        await self.data.async_refresh(reload=_reload)
        return result

    @staticmethod
    async def _json(request: web.Request) -> dict:
        try:
            body = await request.json()
        except ValueError:
            raise ValueError("invalid JSON")
        if not isinstance(body, dict):
            raise ValueError("JSON object expected")
        return body

    async def _body_write(self, request, func, *args, status=200, _reload=False, **_):
        try:
            body = await self._json(request)
        except ValueError as e:
            return _err(400, str(e))
        res = await self._write(request, func, *args, body, _reload=_reload)
        if isinstance(res, web.Response):
            return res
        return _err(404, "not found") if res is None else web.json_response(res, status=status)


def _filters(request: web.Request) -> dict:
    keys = ("person", "role", "filament", "printer", "status", "paid", "from", "to", "min_duration", "max_duration", "q")
    return {k: request.query[k] for k in keys if k in request.query}


class PrintsView(_Base):
    url, name = "/api/print_log/prints", "api:print_log:prints"

    async def get(self, request):
        q = request.query
        try:
            res = await self._run(
                self.data.store.list_prints, _filters(request), min(int(q.get("limit", 50)), 1000),
                int(q.get("offset", 0)), q.get("sort", "ended_at"), q.get("order", "desc") != "asc")
        except (ValueError, TypeError) as e:
            return _err(400, str(e))
        return web.json_response(res)

    async def post(self, request):
        return await self._body_write(request, self._add, status=201)

    def _add(self, body):
        body.setdefault("source", "manual")
        return self.data.store.add_print(body)


class PrintView(_Base):
    url, name = "/api/print_log/prints/{item_id}", "api:print_log:print"

    async def get(self, request, item_id):
        row = await self._run(self.data.store.get_print, int(item_id))
        return web.json_response(row) if row else _err(404, "not found")

    async def put(self, request, item_id):
        return await self._body_write(request, self.data.store.update_print, int(item_id))

    async def delete(self, request, item_id):
        res = await self._write(request, self.data.store.delete_print, int(item_id))
        if isinstance(res, web.Response):
            return res
        return web.json_response({"deleted": True}) if res else _err(404, "not found")


class PaidView(_Base):
    """Bulk mark prints as paid / unpaid: POST {"ids": [1, 2], "paid": true}."""
    url, name = "/api/print_log/paid", "api:print_log:paid"

    async def post(self, request):
        return await self._body_write(request, self._paid)

    def _paid(self, body):
        ids = body.get("ids")
        if not isinstance(ids, list):
            raise ValueError("ids must be a list")
        return {"updated": self.data.store.mark_paid(ids, bool(body.get("paid", True)))}


class SettlementPreviewView(_Base):
    """Open prints of one person: GET ?person=ID[&period=YYYY-MM]."""
    url, name = "/api/print_log/settlement_preview", "api:print_log:settlement_preview"

    async def get(self, request):
        q = request.query
        try:
            res = await self._run(self.data.store.settlement_preview, int(q.get("person")), q.get("period") or None)
        except (TypeError, ValueError) as e:
            return _err(400, str(e))
        return web.json_response(res)


class SettlementsView(_Base):
    url, name = "/api/print_log/settlements", "api:print_log:settlements"

    async def get(self, request):
        person = request.query.get("person")
        try:
            res = await self._run(self.data.store.list_settlements, int(person) if person else None)
        except (TypeError, ValueError) as e:
            return _err(400, str(e))
        return web.json_response(res)

    async def post(self, request):
        return await self._body_write(request, self._settle, status=201)

    def _settle(self, body):
        return self.data.store.settle(int(body.get("person_id")), body.get("print_ids") or [],
                                      body.get("final"), body.get("note"), body.get("period"))


class SettlementItemView(_Base):
    url, name = "/api/print_log/settlements/{item_id}", "api:print_log:settlement"

    async def delete(self, request, item_id):
        res = await self._write(request, self.data.store.unsettle, int(item_id))
        if isinstance(res, web.Response):
            return res
        return web.json_response({"deleted": True}) if res else _err(404, "not found")


class SettlementExportView(_Base):
    """GET ?format=csv|html&lang=nl|en. The html page is meant to be printed or saved as PDF from the browser."""
    url, name = "/api/print_log/settlements/{item_id}/export", "api:print_log:settlement_export"

    async def get(self, request, item_id):
        try:
            detail = await self._run(self.data.store.settlement_detail, int(item_id))
        except ValueError:
            return _err(400, "invalid id")
        if not detail:
            return _err(404, "not found")
        lang = request.query.get("lang", "en")
        if request.query.get("format") == "csv":
            return web.Response(text=settlement_csv(detail, lang), content_type="text/csv",
                                headers={"Content-Disposition": f"attachment; filename=settlement_{detail['id']}.csv"})
        return web.Response(text=settlement_html(detail, lang), content_type="text/html")


class ThumbView(_Base):
    """A stored print thumbnail. Needs a login, so the panel loads it with the user's token."""
    url, name = "/api/print_log/thumbs/{filename}", "api:print_log:thumb"

    async def get(self, request, filename):
        path = self.data.store.thumbnail_path(filename)
        if not path:
            return _err(404, "not found")
        body = await self.hass.async_add_executor_job(path.read_bytes)
        ctype = "image/png" if filename.endswith(".png") else "image/jpeg"
        return web.Response(body=body, content_type=ctype, headers={"Cache-Control": "private, max-age=86400"})


class CollectionView(_Base):
    def __init__(self, hass, table: str) -> None:
        super().__init__(hass)
        self.table = table
        self.url = f"/api/print_log/{table}"
        self.name = f"api:print_log:{table}"

    async def get(self, request):
        return web.json_response(await self._run(self.data.store.list_table, self.table, True))

    async def post(self, request):
        return await self._body_write(request, self.data.store.add_item, self.table, status=201,
                                      _reload=self.table == "printers")


class ItemView(_Base):
    def __init__(self, hass, table: str) -> None:
        super().__init__(hass)
        self.table = table
        self.url = f"/api/print_log/{table}/{{item_id}}"
        self.name = f"api:print_log:{table}:item"

    async def put(self, request, item_id):
        return await self._body_write(request, self.data.store.update_item, self.table, int(item_id),
                                      _reload=self.table == "printers")

    async def delete(self, request, item_id):
        res = await self._write(request, self.data.store.delete_item, self.table, int(item_id),
                                _reload=self.table == "printers")
        return res if isinstance(res, web.Response) else web.json_response({"result": res})


class StatsView(_Base):
    url, name = "/api/print_log/stats", "api:print_log:stats"

    async def get(self, request):
        try:
            rows = await self._run(self.data.store.stats, request.query.get("group_by", "person"), _filters(request))
        except ValueError as e:
            return _err(400, str(e))
        return web.json_response(rows)


class ExportView(_Base):
    url, name = "/api/print_log/export.csv", "api:print_log:export"

    async def get(self, request):
        text = await self._run(self.data.store.export_csv, _filters(request))
        return web.Response(text=text, content_type="text/csv",
                            headers={"Content-Disposition": "attachment; filename=print_log.csv"})


class SettingsView(_Base):
    url, name = "/api/print_log/settings", "api:print_log:settings"

    async def get(self, request):
        return web.json_response(await self._run(self.data.store.get_settings))

    async def put(self, request):
        return await self._body_write(request, self.data.store.update_settings, _reload=True)


def async_register_views(hass: HomeAssistant) -> None:
    views: list[HomeAssistantView] = [
        PrintsView(hass), PaidView(hass), PrintView(hass), StatsView(hass), ExportView(hass), SettingsView(hass),
        SettlementPreviewView(hass), SettlementsView(hass), SettlementItemView(hass), SettlementExportView(hass),
        ThumbView(hass)]
    for t in TABLES:
        views += [CollectionView(hass, t), ItemView(hass, t)]
    for v in views:
        hass.http.register_view(v)
