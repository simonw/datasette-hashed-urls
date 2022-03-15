import collections
from datasette import hookimpl
from functools import wraps


@hookimpl
def startup(datasette):
    new_databases = collections.OrderedDict()
    datasette._hashed_url_databases = {}
    for name, database in datasette.databases.items():
        if database.hash:
            assert (
                "_" not in name
            ), 'datasette-hashed-urls does not work with databases with "_" in their name'
            datasette._hashed_url_databases[name] = database.hash[:7]
            new_name = "{}_{}".format(name, database.hash[:7])
            new_databases[new_name] = database
            database.name = new_name
        else:
            new_databases[name] = database
    datasette.databases.clear()
    datasette.databases.update(new_databases)


@hookimpl
def asgi_wrapper(datasette):
    def wrap_with_hashed_urls(app):
        @wraps(app)
        async def hashed_urls(scope, receive, send):
            if scope.get("type") != "http":
                await app(scope, receive, send)
                return
            # Only trigger on pages with a path that starts with /xxx
            # or /xxx_yyy where xxx is the name of an immutable database
            # and where the first page component matches a database name
            path = scope["path"].lstrip("/")
            db_name = path.split("/")[0].split("_")[0]
            if db_name in datasette._hashed_url_databases:
                await handle_hashed_urls(datasette, app, scope, receive, send)
                return
            await app(scope, receive, send)

        return hashed_urls

    return wrap_with_hashed_urls


async def handle_hashed_urls(datasette, app, scope, receive, send):
    path = scope["path"].lstrip("/")
    db_name_and_hash = path.split("/")[0]
    if "_" not in db_name_and_hash:
        db_name = db_name_and_hash
        incoming_hash = ""
    else:
        db_name, _, incoming_hash = db_name_and_hash.partition("_")
    current_hash = datasette._hashed_url_databases[db_name]
    if current_hash != incoming_hash:
        # Send the redirect
        path_bits = path.split("/")
        new_path = "/" + "/".join(
            ["{}_{}".format(db_name, current_hash)] + path_bits[1:]
        )
        if scope.get("query_string"):
            new_path += "?" + scope["query_string"].decode("latin-1")

        await send(
            {
                "type": "http.response.start",
                "status": 302,
                "headers": [[b"location", new_path.encode("latin1")]],
            }
        )
        await send({"type": "http.response.body", "body": b""})
        return
    else:
        # Hash is correct, add a far-future cache header
        async def wrapped_send(event):
            if event["type"] == "http.response.start":
                original_headers = [
                    pair
                    for pair in event.get("headers")
                    if pair[0].lower() != b"cache-control"
                ]
                event = {
                    "type": event["type"],
                    "status": event["status"],
                    "headers": original_headers
                    + [[b"cache-control", "max-age=31536000"]],
                }
            await send(event)

        return await app(scope, receive, wrapped_send)

    await app(scope, receive, send)
