from datasette.app import Datasette
import pytest
import sqlite_utils


@pytest.fixture
def ds(tmpdir):
    mutable = str(tmpdir / "mutable.db")
    immutable = str(tmpdir / "immutable.db")
    rows = [{"id": 1}, {"id": 2}]
    sqlite_utils.Database(mutable)["t"].insert_all(rows, pk="id")
    sqlite_utils.Database(immutable)["t"].insert_all(rows, pk="id")
    ds = Datasette(files=[mutable], immutables=[immutable])
    return ds


@pytest.mark.asyncio
async def test_immutable_database_renamed_on_startup(ds):
    await ds.invoke_startup()
    databases = (await ds.client.get("/-/databases.json")).json()
    names = [db["name"] for db in databases]
    assert len(names) == 2
    assert "mutable" in names
    other_name = [name for name in names if name != "mutable"][0]
    assert other_name.startswith("immutable_")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,should_redirect",
    (
        ("/", False),
        ("/mutable", False),
        ("/mutable/t", False),
        ("/mutable/t/1", False),
        ("/immutable", True),
        ("/immutable/t", True),
        ("/immutable/t?id=1", True),
        ("/immutable/t/1", True),
    ),
)
async def test_paths_with_no_hash_redirect(ds, path, should_redirect):
    await ds.invoke_startup()
    immutable_hash = ds._hashed_url_databases["immutable"]
    response = await ds.client.get(path)
    assert (
        "cache-control" not in response.headers
        or response.headers["cache-control"] == "max-age=5"
    )
    if should_redirect:
        assert response.status_code == 302
        expected_path = path.replace(
            "/immutable", "/immutable_{}".format(immutable_hash)
        )
        assert response.headers["location"] == expected_path
    else:
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("path_suffix", ("", "/t", "/t?id=1", "/t/1"))
async def test_paths_with_hash_have_cache_header(ds, path_suffix):
    await ds.invoke_startup()
    immutable_hash = ds._hashed_url_databases["immutable"]
    path = "/immutable_{}{}".format(immutable_hash, path_suffix)
    response = await ds.client.get(path)
    assert response.status_code == 200
    cache_control = response.headers["cache-control"]
    assert cache_control == "max-age=31536000"


@pytest.mark.asyncio
async def test_error_if_db_contains_underscore(tmpdir):
    bad_db = str(tmpdir / "bad_db.db")
    sqlite_utils.Database(bad_db)["t"].insert_all([{"id": 1}], pk="id")
    ds = Datasette(files=[], immutables=[bad_db])
    with pytest.raises(AssertionError) as e:
        await ds.invoke_startup()
    assert (
        e.value.args[0]
        == 'datasette-hashed-urls does not work with databases with "_" in their name'
    )
