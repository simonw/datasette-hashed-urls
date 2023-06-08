from datasette.app import Datasette
import pytest
import pytest_asyncio
import sqlite_utils


@pytest.fixture
def db_files(tmpdir):
    mutable = str(tmpdir / "this-is-mutable.db")
    immutable = str(tmpdir / "this-is-immutable.db")
    rows = [{"id": 1}, {"id": 2}]
    sqlite_utils.Database(mutable)["t"].insert_all(rows, pk="id")
    sqlite_utils.Database(immutable)["t"].insert_all(rows, pk="id")
    return mutable, immutable


@pytest_asyncio.fixture
async def ds(db_files):
    ds = Datasette(files=[db_files[0]], immutables=[db_files[1]], crossdb=True)
    await ds.invoke_startup()
    return ds


@pytest.mark.asyncio
async def test_immutable_database_has_new_route_on_startup(ds):

    route = ds.databases["this-is-immutable"].route
    assert route.startswith("this-is-immutable-")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,should_redirect",
    (
        ("/", False),
        ("/this-is-mutable", False),
        ("/this-is-mutable?sql=select+1", False),
        ("/this-is-mutable.json?sql=select+1", False),
        ("/this-is-mutable/t", False),
        ("/this-is-mutable/t/1", False),
        ("/this-is-immutable", True),
        ("/this-is-immutable?sql=select+1", True),
        ("/this-is-immutable.json?sql=select+1", True),
        ("/this-is-immutable/t", True),
        ("/this-is-immutable/t?id=1", True),
        ("/this-is-immutable/t/1", True),
    ),
)
async def test_paths_with_no_hash_redirect(ds, path, should_redirect):
    immutable_hash = ds._hashed_url_databases["this-is-immutable"]
    response = await ds.client.get(path)
    assert (
        "cache-control" not in response.headers
        or response.headers["cache-control"] == "max-age=5"
    )
    if should_redirect:
        assert response.status_code == 302
        expected_path = path.replace(
            "/this-is-immutable", "/this-is-immutable-{}".format(immutable_hash)
        )
        assert response.headers["location"] == expected_path
        # Fetch that one too and make sure it is 200
        second_response = await ds.client.get(response.headers["location"])
        assert second_response.status_code == 200
    else:
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("path_suffix", ("", "/t", "/t?id=1", "/t/1"))
@pytest.mark.parametrize("max_age", (None, 3600))
async def test_paths_with_hash_have_cache_header(db_files, path_suffix, max_age):
    metadata = {}
    if max_age:
        metadata["plugins"] = {"datasette-hashed-urls": {"max_age": max_age}}
    ds = Datasette(files=[db_files[0]], immutables=[db_files[1]], metadata=metadata)
    await ds.invoke_startup()
    immutable_hash = ds._hashed_url_databases["this-is-immutable"]
    path = "/this-is-immutable-{}{}".format(immutable_hash, path_suffix)
    response = await ds.client.get(path)
    assert response.status_code == 200
    cache_control = response.headers["cache-control"]
    expected = "max-age={}, public".format(max_age or 31536000)
    assert cache_control == expected


@pytest.mark.asyncio
async def test_index_page(ds):
    hash = ds.get_database("this-is-immutable").hash[:7]
    response = await ds.client.get("/")
    assert (
        '<a href="/this-is-immutable-{}">this-is-immutable</a>'.format(hash)
        in response.text
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ("/", "/this-is-immutable", "/this-is-immutable/t", "/this-is-immutable/t/1"),
)
async def test_links_on_pages(ds, path):
    hash = ds.get_database("this-is-immutable").hash[:7]
    response = await ds.client.get(path, follow_redirects=True)
    assert "/this-is-immutable-{}".format(hash) in response.text


@pytest.mark.asyncio
async def test_crossdb(ds):
    response = await ds.client.get(
        "/_memory.json",
        params={
            "sql": "select * from [this-is-mutable].t union all select * from [this-is-immutable].t",
            "_shape": "array",
        },
    )
    # Should redirect
    assert response.status_code == 302
    path = response.headers["location"]
    assert path.startswith("/_memory-")
    response2 = await ds.client.get(path)
    assert response2.json() == [{"id": 1}, {"id": 2}, {"id": 1}, {"id": 2}]


@pytest.mark.asyncio
@pytest.mark.parametrize("should_cors", (True, False))
async def test_cors_headers_on_redirect(ds, should_cors):
    ds.cors = should_cors
    response = await ds.client.get("/this-is-immutable.json?sql=select+1")
    cors_headers = {
        "access-control-allow-origin": "*",
        "access-control-allow-headers": "authorization",
        "access-control-expose-headers": "link",
    }
    if should_cors:
        for key, value in cors_headers.items():
            assert response.headers[key] == value
    else:
        for key in cors_headers:
            assert key not in response.headers


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_on_errors", (True, False))
async def test_cache_on_errors(db_files, cache_on_errors):
    metadata = {}
    metadata["plugins"] = {"datasette-hashed-urls": {"cache_on_errors": cache_on_errors}}
    ds = Datasette(files=[db_files[0]], immutables=[db_files[1]], metadata=metadata)
    await ds.invoke_startup()
    immutable_hash = ds._hashed_url_databases["this-is-immutable"]
    path = "/this-is-immutable-{}{}".format(immutable_hash, ".json?sql=error")
    response = await ds.client.get(path)
    assert response.status_code == 400
    assert (
        response.headers["cache-control"] == "max-age=31536000, public"
    ) if cache_on_errors else (
        "cache-control" not in response.headers
        or response.headers["cache-control"] == "max-age=5"
    )