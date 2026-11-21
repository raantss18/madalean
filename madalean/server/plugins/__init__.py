"""Server plugins: every module in this package that defines `register(app, ctx)` is called by `make_app`.

A plugin adds routes (`app.router.add_get("/api/…", handler)`; handlers reach the context with
`request.app[madalean.server.common.CTX]`, mark host-only handlers with `madalean.server.common.host_only`) and
publishes WebSocket events with `ctx.publish("<type>", {...})`. See docs/API.md « Plugins »."""
