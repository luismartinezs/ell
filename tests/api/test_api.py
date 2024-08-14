from datetime import timezone
from logging import DEBUG
from uuid import uuid4
import pytest
from typing import Any, Dict
from fastapi.testclient import TestClient
from sqlmodel import Session
from ell.api.server import NoopPublisher, create_app, get_publisher, get_serializer, get_session
from ell.api.config import Config
from ell.api.types import WriteLMPInput

from ell.stores.sql import SQLStore, SQLiteStore
from ell.studio.logger import setup_logging
from ell.types import SerializedLMP, utc_now 


@pytest.fixture
def sql_store() -> SQLStore:
    return SQLiteStore(":memory:")

def test_construct_serialized_lmp():
    serialized_lmp = SerializedLMP(
        lmp_id="test_lmp_id",
        name="Test LMP",
        source="def test_function(): pass",
        dependencies=str(["dep1", "dep2"]),
        lm_kwargs={"param1": "value1"},
        is_lm=True,
        version_number=1,
        # uses={"used_lmp_1": {}, "used_lmp_2": {}},
        initial_global_vars={"global_var1": "value1"},
        initial_free_vars={"free_var1": "value2"},
        commit_message="Initial commit",
        created_at=utc_now()
    )
    assert serialized_lmp.lmp_id == "test_lmp_id"
    assert serialized_lmp.name == "Test LMP"
    assert serialized_lmp.source == "def test_function(): pass"
    assert serialized_lmp.dependencies == str(["dep1", "dep2"])
    assert serialized_lmp.lm_kwargs == {"param1": "value1"}
    assert serialized_lmp.version_number == 1
    assert serialized_lmp.created_at is not None

def test_write_lmp_input():
    ## Should be able to construct a WriteLMPInput from data
    input = WriteLMPInput(
        lmp_id="test_lmp_id",
        name="Test LMP",
        source="def test_function(): pass",
        dependencies=str(["dep1", "dep2"]),
        is_lm=True,
        lm_kwargs={"param1": "value1"},
        initial_global_vars={"global_var1": "value1"},
        initial_free_vars={"free_var1": "value2"},
        commit_message="Initial commit",
        version_number=1,
    )

    # Should default a created_at to utc_now
    assert input.created_at is not None
    assert input.created_at.tzinfo == timezone.utc

    ## Should be able to construct a SerializedLMP from a WriteLMPInput
    model = SerializedLMP(**input.model_dump())
    assert model.created_at == input.created_at

    input2 = WriteLMPInput(
        lmp_id="test_lmp_id",
        name="Test LMP",
        source="def test_function(): pass",
        dependencies=str(["dep1", "dep2"]),
        is_lm=True,
        lm_kwargs={"param1": "value1"},
        initial_global_vars={"global_var1": "value1"},
        initial_free_vars={"free_var1": "value2"},
        commit_message="Initial commit",
        version_number=1,
        # should work with an isoformat string
        created_at=utc_now().isoformat() # type: ignore
    )
    model2 = SerializedLMP(**input2.model_dump())
    assert model2.created_at == input2.created_at
    assert input2.created_at is not None
    assert input2.created_at.tzinfo == timezone.utc



def test_write_lmp(sql_store: SQLStore):
    setup_logging(DEBUG)
    config = Config(storage_dir=":memory:")
    app = create_app(config)

    publisher = NoopPublisher()
    async def get_publisher_override():
        yield publisher

    async def get_session_override():
        with Session(sql_store.engine) as session:
            yield session
        
    def get_serializer_override():
        return sql_store

    app.dependency_overrides[get_publisher] = get_publisher_override
    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_serializer] = get_serializer_override

    client = TestClient(app)

    
    lmp_data:Dict[str, Any] = {
        "lmp_id": uuid4().hex,
        "name": "Test LMP",
        "source": "def test_function(): pass",
        "dependencies": str(["dep1", "dep2"]),
        "is_lm": True,
        "lm_kwargs": {"param1": "value1"},
        "version_number": 1,
        "uses": {"used_lmp_1": {}, "used_lmp_2": {}},
        "initial_global_vars": {"global_var1": "value1"},
        "initial_free_vars": {"free_var1": "value2"},
        "commit_message": "Initial commit",
        "created_at": utc_now().isoformat().replace("+00:00", "Z")
    }
    uses:Dict[str, Any] = {
        "used_lmp_1": {},
        "used_lmp_2": {}
    }

    response = client.post(
        "/lmp",
        json={
            "lmp": lmp_data,
            "uses": uses    
        }
    )

    assert response.status_code == 200

    lmp = client.get(f"/lmp/{lmp_data['lmp_id']}")
    assert lmp.status_code == 200
    del lmp_data["uses"]
    assert lmp.json() == {**lmp_data, "num_invocations": 0}

def test_write_invocation(sql_store: SQLStore):
    config = Config(storage_dir=":memory:")
    app = create_app(config)
    client = TestClient(app)

    invocation_data = {
        "lmp_id": "test_lmp_id",
        "name": "Test Invocation",
        "description": "This is a test invocation"
    }
    results_data = [
        {
            "result_id": "test_result_id",
            "name": "Test Result",
            "description": "This is a test result"
        }
    ]
    consumes_data = ["test_consumes_id"]

    response = client.post(
        "/invocation",
        json={
            "invocation": invocation_data,
            "results": results_data,
            "consumes": consumes_data
        }
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Invocation written successfully"}

if __name__ == "__main__":
    pytest.main()