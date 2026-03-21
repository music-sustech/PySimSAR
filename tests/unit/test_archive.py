import json

import numpy as np
import pytest

from pySimSAR.io.archive import pack_project, unpack_project


def test_roundtrip(tmp_path):
    """Pack a project dir, unpack to new location, verify all files identical."""
    # Create a sample project directory
    proj_dir = tmp_path / "my_project"
    proj_dir.mkdir()

    # project.json
    project_data = {"format_version": "1.0", "name": "test"}
    (proj_dir / "project.json").write_text(json.dumps(project_data))

    # scene.json
    scene_data = {"origin_lat_deg": 48.0, "origin_lon_deg": 11.0}
    (proj_dir / "scene.json").write_text(json.dumps(scene_data))

    # binary data
    arr = np.random.rand(10, 10)
    np.save(str(proj_dir / "data.npy"), arr)

    # Pack
    archive_path = tmp_path / "test.pysimsar"
    pack_project(proj_dir, archive_path)
    assert archive_path.exists()

    # Unpack
    out_dir = tmp_path / "unpacked"
    unpack_project(archive_path, out_dir)

    # Verify
    assert (out_dir / "project.json").exists()
    restored = json.loads((out_dir / "project.json").read_text())
    assert restored == project_data

    restored_arr = np.load(str(out_dir / "data.npy"))
    np.testing.assert_array_equal(arr, restored_arr)

def test_pack_not_a_directory(tmp_path):
    with pytest.raises(ValueError, match="Not a directory"):
        pack_project(tmp_path / "nonexistent", tmp_path / "out.pysimsar")

def test_unpack_not_a_file(tmp_path):
    with pytest.raises(ValueError, match="Not a file"):
        unpack_project(tmp_path / "nonexistent.pysimsar", tmp_path / "out")
