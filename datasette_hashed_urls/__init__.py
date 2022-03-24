from datasette import hookimpl
from functools import wraps
import hashlib


@hookimpl
def startup(datasette):
    datasette._hashed_url_databases = {}
    all_hashes = []
    for name, database in datasette.databases.items():
        if database.hash:
            all_hashes.append(database.hash)
            hash = database.hash[:7]
            datasette._hashed_url_databases[name] = hash
            route = "{}-{}".format(name, hash)
            database.route = route
            datasette._hashed_url_databases[name] = hash
    if datasette.crossdb and all_hashes:
        # Set up a hashed route for _memory too, as a combo
        # of all of the other hashes
        memory_hash = hashlib.sha256(
            "\n".join(all_hashes).encode("latin-1")
        ).hexdigest()[:7]
        memory = datasette.get_database("_memory")
        memory.route = "_memory-{}".format(memory_hash)
        datasette._hashed_url_databases["_memory"] = memory_hash


@hookimpl
def asgi_wrapper(datasette):
    def wrap_with_hashed_urls(app):
        @wraps(app)
        async def hashed_urls(scope, receive, send):
            if scope.get("type") != "http":
                await app(scope, receive, send)
                return
            # Only trigger on pages with a path that starts with /xxx
            # or /xxx-yyy where xxx is the name of an immutable database
            # and where the first page component matches a database name
            path = scope["path"].lstrip("/")
            first_component = path.split("/")[0]
            # Might have a format like .json on the end
            first_component_without_format = first_component.split(".")[0]
            db_without_hash_or_format = first_component_without_format.rsplit("-", 1)[0]
            if (first_component_without_format in datasette._hashed_url_databases) or (
                db_without_hash_or_format in datasette._hashed_url_databases
            ):
                await handle_hashed_urls(datasette, app, scope, receive, send)
                return
            await app(scope, receive, send)

        return hashed_urls

    return wrap_with_hashed_urls


async def handle_hashed_urls(datasette, app, scope, receive, send):
    path = scope["path"].lstrip("/")
    first_component = path.split("/")[0]

    if "." in first_component:
        first_component_without_format, _, format = first_component.partition(".")
    else:
        first_component_without_format = first_component
        format = None

    if ("-" not in first_component_without_format) or (
        first_component_without_format in datasette._hashed_url_databases
    ):
        db_name = first_component_without_format
        incoming_hash = ""
    else:
        db_name, incoming_hash = first_component_without_format.rsplit("-", 1)

    current_hash = datasette._hashed_url_databases[db_name]
    if current_hash != incoming_hash:
        # Send the redirect
        path_bits = path.split("/")

        new_path = "/" + "/".join(
            [
                "{}-{}{}".format(
                    db_name, current_hash, ".{}".format(format) if format else ""
                )
            ]
            + path_bits[1:]
        )
        if scope.get("query_string"):
            new_path += "?" + scope["query_string"].decode("latin-1")

        redirect_headers = [[b"location", new_path.encode("latin1")]]
        if datasette.cors:
            redirect_headers.extend(
                [
                    [b"access-control-allow-origin", b"*"],
                    [b"access-control-allow-headers", b"authorization"],
                    [b"access-control-expose-headers", b"link"],
                ]
            )

        await send(
            {
                "type": "http.response.start",
                "status": 302,
                "headers": redirect_headers,
            }
        )
        await send({"type": "http.response.body", "body": b""})
        return
    else:
        plugin_config = datasette.plugin_config("datasette-hashed-urls") or {}
        max_age = plugin_config.get("max_age", 31536000)

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
                    + [
                        [
                            b"cache-control",
                            "max-age={}, public".format(max_age).encode("latin-1"),
                        ]
                    ],
                }
            await send(event)

        return await app(scope, receive, wrapped_send)
