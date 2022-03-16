from datasette.app import Datasette
import pytest
import sqlite_utils


@pytest.fixture
def db_files(tmpdir):
    mutable = str(tmpdir / "this-is-mutable.db")
    immutable = str(tmpdir / "this-is-immutable.db")
    rows = [{"id": 1}, {"id": 2}]
    sqlite_utils.Database(mutable)["t"].insert_all(rows, pk="id")
    sqlite_utils.Database(immutable)["t"].insert_all(rows, pk="id")
    return mutable, immutable


@pytest.fixture
def ds(db_files):
    return Datasette(files=[db_files[0]], immutables=[db_files[1]])


@pytest.mark.asyncio
async def test_immutable_database_renamed_on_startup(ds):
    await ds.invoke_startup()
    databases = (await ds.client.get("/-/databases.json")).json()
    names = [db["name"] for db in databases]
    assert len(names) == 2
    assert "this-is-mutable" in names
    other_name = [name for name in names if name != "this-is-mutable"][0]
    assert other_name.startswith("this-is-immutable-")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,should_redirect",
    (
        ("/", False),
        ("/this-is-mutable", False),
        ("/this-is-mutable/t", False),
        ("/this-is-mutable/t/1", False),
        ("/this-is-immutable", True),
        ("/this-is-immutable/t", True),
        ("/this-is-immutable/t?id=1", True),
        ("/this-is-immutable/t/1", True),
    ),
)
async def test_paths_with_no_hash_redirect(ds, path, should_redirect):
    await ds.invoke_startup()
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
