"""Offline tests for MHO98 binary downloads."""

import hashlib
from pathlib import Path

import pytest

from rigol_mcp.mho98.binary import download_binary, restore_setup


class FakeSession:
    def __init__(self, output_dir, payload=b"payload"):
        self.output_dir = Path(output_dir)
        self.payload = payload
        self.calls = []
        self.binary_writes = []

    def binary_query(self, command, max_bytes):
        self.calls.append((command, max_bytes))
        if len(self.payload) > max_bytes:
            raise ValueError("oversize")
        return self.payload

    def write_binary(self, command, payload, max_bytes):
        self.binary_writes.append((command, bytes(payload), max_bytes))


def test_bus_data_download_uses_correct_query_and_metadata(tmp_path):
    payload = b"PARALLEL\nTime,Data,\n"
    session = FakeSession(tmp_path, payload)

    result = download_binary(session, "bus_data", bus=3, filename="capture")

    assert session.calls == [(":BUS3:DATA?", 16 * 1024 * 1024)]
    assert Path(result["path"]).suffix == ".bin"
    assert Path(result["path"]).read_bytes() == payload
    assert result["reply_kind"] == "bus_data"
    assert result["bytes"] == len(payload)
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    ("payload", "suffix"),
    [(b"\x89PNG\r\n\x1a\nimage", ".png"), (b"\xff\xd8\xffimage", ".jpg"), (b"BMimage", ".bmp")],
)
def test_saved_image_uses_detected_format_suffix(tmp_path, payload, suffix):
    session = FakeSession(tmp_path, payload)

    result = download_binary(session, "saved_image")

    assert session.calls[0][0] == ":SAVE:IMAGe:DATA?"
    assert Path(result["path"]).suffix == suffix


def test_setup_download_has_stp_suffix_and_no_device_write(tmp_path):
    session = FakeSession(tmp_path, b"setup-data")

    result = download_binary(session, "setup", filename="setup")

    assert session.calls == [(":SYSTem:SETup?", 16 * 1024 * 1024)]
    assert Path(result["path"]).suffix == ".stp"


def test_invalid_limits_bus_and_path_are_rejected_before_binary_query(tmp_path):
    session = FakeSession(tmp_path)
    with pytest.raises(ValueError, match="bus"):
        download_binary(session, "bus_data", bus=5)
    with pytest.raises(ValueError, match="64 MiB"):
        download_binary(session, "setup", max_bytes=64 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="inside output_dir"):
        download_binary(session, "setup", filename="../escape.bin")
    assert session.calls == []


def test_existing_file_is_never_overwritten(tmp_path):
    target = tmp_path / "setup.bin"
    target.write_bytes(b"original")
    session = FakeSession(tmp_path, b"new")

    with pytest.raises(FileExistsError):
        download_binary(session, "setup", filename="setup.bin")
    assert target.read_bytes() == b"original"


def test_restore_setup_uploads_one_bounded_binary_payload(tmp_path):
    payload = b"setup-binary"
    path = tmp_path / "saved.stp"
    path.write_bytes(payload)
    session = FakeSession(tmp_path)

    result = restore_setup(session, "saved.stp")

    assert session.binary_writes == [(
        ":SYSTem:SETup",
        payload,
        64 * 1024 * 1024,
    )]
    assert result["restored"] is True
    assert result["bytes"] == len(payload)
    assert result["sha256"] == hashlib.sha256(payload).hexdigest()


def test_restore_setup_rejects_empty_traversal_and_symlink(tmp_path):
    session = FakeSession(tmp_path)
    (tmp_path / "empty.stp").write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        restore_setup(session, "empty.stp")
    with pytest.raises(ValueError, match="inside output_dir"):
        restore_setup(session, "../outside.stp")
    outside = tmp_path.parent / "outside-setup.stp"
    outside.write_bytes(b"outside")
    link = tmp_path / "link.stp"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        restore_setup(session, "link.stp")
