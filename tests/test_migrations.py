"""Tests verifying Alembic database migrations and baseline schema integrity."""
import os
import shutil
import subprocess
import sys


def _get_alembic_cmd():
    res = subprocess.run([sys.executable, '-m', 'alembic', '--version'], capture_output=True)
    if res.returncode == 0:
        return [sys.executable, '-m', 'alembic']
    alembic_path = shutil.which('alembic')
    if alembic_path:
        return [alembic_path]
    return [sys.executable, '-m', 'alembic']


def test_alembic_configuration_files_exist():
    """Verify alembic.ini and migration environment files exist."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    assert os.path.isfile(os.path.join(base_dir, 'alembic.ini'))
    assert os.path.isdir(os.path.join(base_dir, 'migrations'))
    assert os.path.isfile(os.path.join(base_dir, 'migrations', 'env.py'))
    assert os.path.isfile(os.path.join(base_dir, 'migrations', 'script.py.mako'))


def test_baseline_migration_covers_required_tables():
    """Verify baseline migration defines players, game_scores, and gameplay tables."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    versions_dir = os.path.join(base_dir, 'migrations', 'versions')
    
    version_files = [f for f in os.listdir(versions_dir) if f.endswith('.py') and not f.startswith('__')]
    assert len(version_files) >= 1, "At least one migration revision must exist"

    baseline_path = os.path.join(versions_dir, version_files[0])
    with open(baseline_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Verify tables defined in baseline migration
    assert "op.create_table('players'" in content or 'create_table("players"' in content
    assert "op.create_table('game_scores'" in content or 'create_table("game_scores"' in content
    assert "op.create_table('gameplay'" in content or 'create_table("gameplay"' in content
    assert "op.create_table('games'" in content or 'create_table("games"' in content


def test_alembic_check_passes(tmp_path):
    """Verify that current SQLAlchemy models match Alembic migration state with no drift."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    test_db = tmp_path / "test_check.db"
    env = os.environ.copy()
    env['DATABASE_URL'] = f"sqlite:///{test_db}"

    # Bring target test database to latest migration head
    up_res = subprocess.run(
        _get_alembic_cmd() + ['upgrade', 'head'],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True
    )
    assert up_res.returncode == 0, f"Alembic upgrade failed before check:\n{up_res.stdout}\n{up_res.stderr}"

    # Verify model vs migration schema drift
    res = subprocess.run(
        _get_alembic_cmd() + ['check'],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"Alembic check failed:\n{res.stdout}\n{res.stderr}"
    assert "No new upgrade operations detected" in res.stdout or res.returncode == 0


def test_alembic_upgrade_and_downgrade_cycle(tmp_path):
    """Verify baseline migration executes full upgrade and downgrade lifecycle on fresh database."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    test_db = tmp_path / "test_migration_cycle.db"
    env = os.environ.copy()
    env['DATABASE_URL'] = f"sqlite:///{test_db}"

    # Upgrade to head
    up_res = subprocess.run(
        _get_alembic_cmd() + ['upgrade', 'head'],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True
    )
    assert up_res.returncode == 0, f"Alembic upgrade failed:\n{up_res.stdout}\n{up_res.stderr}"

    # Downgrade back to base
    down_res = subprocess.run(
        _get_alembic_cmd() + ['downgrade', 'base'],
        cwd=base_dir,
        env=env,
        capture_output=True,
        text=True
    )
    assert down_res.returncode == 0, f"Alembic downgrade failed:\n{down_res.stdout}\n{down_res.stderr}"

