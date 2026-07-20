from flask import Response, jsonify, request, send_file, stream_with_context

from .iptv_xtream import XtreamError


def _iter_upstream_chunks(upstream, chunk_size=64 * 1024):
    reader = getattr(upstream, "read1", None) or upstream.read
    try:
        while True:
            chunk = reader(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        upstream.close()


def register_iptv_routes(app, service_provider):
    def current_service():
        return service_provider() if callable(service_provider) else service_provider

    @app.route("/api/iptv/config", methods=["GET", "POST", "DELETE"])
    def iptv_config():
        service = current_service()
        if request.method == "GET":
            return jsonify(service.public_config())
        if request.method == "DELETE":
            return jsonify({"success": True, **service.save_config("", clear=True)})
        data = request.get_json(silent=True) or {}
        try:
            saved = service.save_config(
                data.get("server_url"),
                data.get("username"),
                data.get("password"),
                data.get("allow_insecure_tls"),
            )
            return jsonify({"success": True, **saved})
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/iptv/test")
    def iptv_test():
        service = current_service()
        try:
            return jsonify(service.test_connection())
        except (ValueError, XtreamError) as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/iptv/sync")
    def iptv_sync():
        service = current_service()
        try:
            started = service.start_sync()
            return jsonify({"accepted": started, "status": service.status()})
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/status")
    def iptv_status():
        service = current_service()
        return jsonify(service.status())

    @app.get("/api/iptv/categories")
    def iptv_categories():
        service = current_service()
        try:
            return jsonify({"items": service.store.categories(request.args.get("kind", "live"))})
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/items")
    def iptv_items():
        service = current_service()
        try:
            return jsonify(service.list_items(
                request.args.get("kind", "live"),
                category_id=request.args.get("category_id", ""),
                query=request.args.get("q", ""),
                page=request.args.get("page", 1),
                page_size=request.args.get("page_size", 30),
                favorites_only=request.args.get("favorites", "").lower() in {"1", "true", "yes"},
            ))
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/favorites")
    def iptv_favorites():
        service = current_service()
        try:
            return jsonify(service.list_favorites(
                kind=request.args.get("kind", ""),
                query=request.args.get("q", ""),
                page=request.args.get("page", 1),
                page_size=request.args.get("page_size", 60),
            ))
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/items/<kind>/<item_id>")
    def iptv_item_detail(kind, item_id):
        service = current_service()
        try:
            return jsonify(service.detail(kind, item_id))
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404
        except (ValueError, XtreamError) as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/epg/<stream_id>")
    def iptv_epg(stream_id):
        service = current_service()
        try:
            return jsonify({"items": service.epg(stream_id, request.args.get("limit", 4))})
        except (ValueError, XtreamError) as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/iptv/favorites/<kind>/<item_id>")
    def iptv_favorite(kind, item_id):
        service = current_service()
        data = request.get_json(silent=True) or {}
        try:
            favorite = service.set_favorite(kind, item_id, bool(data.get("favorite", True)))
            return jsonify({"success": True, "favorite": favorite})
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404

    @app.route("/api/iptv/lists", methods=["GET", "POST"])
    def iptv_lists():
        service = current_service()
        try:
            if request.method == "POST":
                data = request.get_json(silent=True) or {}
                return jsonify(service.create_list(data.get("name", ""))), 201
            return jsonify({"items": service.lists(
                kind=request.args.get("kind", ""),
                item_id=request.args.get("item_id", ""),
                include_system=request.args.get("include_system", "").lower() in {"1", "true", "yes"},
            )})
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.route("/api/iptv/lists/<list_id>", methods=["PATCH", "DELETE"])
    def iptv_list_detail(list_id):
        service = current_service()
        try:
            if request.method == "DELETE":
                return jsonify({"success": service.delete_list(list_id)})
            data = request.get_json(silent=True) or {}
            return jsonify(service.rename_list(list_id, data.get("name", "")))
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/lists/<list_id>/items")
    def iptv_list_items(list_id):
        service = current_service()
        try:
            return jsonify(service.list_entries(
                list_id,
                kind=request.args.get("kind", ""),
                query=request.args.get("q", ""),
                page=request.args.get("page", 1),
                page_size=request.args.get("page_size", 60),
            ))
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    @app.route("/api/iptv/lists/<list_id>/items/<kind>/<item_id>", methods=["POST", "DELETE", "PATCH"])
    def iptv_list_item(list_id, kind, item_id):
        service = current_service()
        data = request.get_json(silent=True) or {}
        try:
            if request.method == "PATCH":
                changed = service.move_list_item(list_id, kind, item_id, data.get("direction"))
            else:
                changed = service.set_list_item(list_id, kind, item_id, request.method == "POST")
            return jsonify({"success": True, "changed": bool(changed)})
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    @app.post("/api/iptv/history/<kind>/<item_id>")
    def iptv_history(kind, item_id):
        service = current_service()
        data = request.get_json(silent=True) or {}
        try:
            service.store.update_history(kind, item_id, data.get("position_seconds"), data.get("duration_seconds"), data.get("completed"))
            return jsonify({"success": True})
        except (KeyError, TypeError, ValueError) as error:
            return jsonify({"error": str(error).strip("'")}), 400

    @app.get("/api/iptv/recent")
    def iptv_recent():
        service = current_service()
        try:
            return jsonify({"items": service.recent(request.args.get("limit", 12))})
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/image/<kind>/<item_id>")
    def iptv_image(kind, item_id):
        service = current_service()
        try:
            path = service.cached_image(kind, item_id, backdrop=request.args.get("backdrop") == "1")
            return send_file(path, max_age=86400, conditional=True)
        except (FileNotFoundError, ValueError):
            return "", 404

    @app.post("/api/iptv/playback")
    def iptv_playback_start():
        service = current_service()
        data = request.get_json(silent=True) or {}
        try:
            port = request.environ.get("SERVER_PORT") or "5000"
            local_base_url = f"http://127.0.0.1:{port}"
            return jsonify(service.start_playback(
                data.get("kind"),
                data.get("item_id"),
                data.get("extension"),
                data.get("title"),
                local_base_url=local_base_url,
            ))
        except KeyError as error:
            return jsonify({"error": str(error).strip("'")}), 404
        except (ValueError, RuntimeError, XtreamError) as error:
            return jsonify({"error": str(error)}), 400

    @app.get("/api/iptv/playback/<token>/<filename>")
    def iptv_playback_file(token, filename):
        service = current_service()
        try:
            path = service.playback_file(token, filename)
            response = send_file(path, conditional=False)
            response.headers["Cache-Control"] = "no-store" if filename.endswith(".m3u8") else "public, max-age=60"
            return response
        except FileNotFoundError:
            return "", 404

    @app.get("/api/iptv/upstream/<token>")
    def iptv_playback_upstream(token):
        service = current_service()
        try:
            upstream = service.open_upstream(token, request.headers.get("Range", ""))
        except FileNotFoundError:
            return "", 404

        headers = {}
        for name in ("Content-Length", "Content-Range", "Accept-Ranges"):
            value = upstream.headers.get(name)
            if value:
                headers[name] = value
        return Response(
            stream_with_context(_iter_upstream_chunks(upstream)),
            status=getattr(upstream, "status", 200),
            content_type=upstream.headers.get("Content-Type", "application/octet-stream"),
            headers=headers,
            direct_passthrough=True,
        )

    @app.delete("/api/iptv/playback/<token>")
    def iptv_playback_stop(token):
        service = current_service()
        return jsonify({"success": service.stop_playback(token)})
