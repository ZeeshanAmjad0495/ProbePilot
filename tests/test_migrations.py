from alembic.script import ScriptDirectory
from alembic.config import Config


def test_single_alembic_head():
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly one alembic head, found: {heads}"
