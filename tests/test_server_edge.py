"""Adversarial tests documenting suspected edge-case bugs in server.py.

Each test is marked xfail(strict=True) and describes a specific bug. When a
bug is fixed, the test will XPASS, forcing the xfail marker to be removed.
"""

import http.client
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import server


@pytest.fixture(scope="module")
def test_server():
    port = 18236
    srv = server.HTTPServer(("127.0.0.1", port), server.FinderHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="fp_edge_")
    os.makedirs(os.path.join(d, "subdir"))
    with open(os.path.join(d, "file.txt"), "w") as f:
        f.write("hello world")  # 11 bytes
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _fs_is_case_insensitive(path):
    probe = os.path.join(path, "CaSeProbe.tmp")
    with open(probe, "w") as f:
        f.write("x")
    try:
        return os.path.exists(os.path.join(path, "caseprobe.tmp"))
    finally:
        os.remove(probe)


# Bug 1: Range request with start > end yields a negative Content-Length.
# serve_file computes length = end - start + 1 without validating start <= end,
# so "bytes=5-3" returns 206 with Content-Length: -1. Per RFC 9110 §14.1.1 an
# unsatisfiable range must return 416.
@pytest.mark.xfail(
    strict=True,
    reason="bug: reversed Range (start>end) returns 206 with negative Content-Length",
)
def test_reversed_range_is_unsatisfiable(test_server, temp_dir):
    path = os.path.join(temp_dir, "file.txt")
    url = f"{test_server}/api/file?path={urllib.parse.quote(path)}"
    req = urllib.request.Request(url, headers={"Range": "bytes=5-3"})
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        assert e.code == 416
        return
    content_length = int(resp.headers.get("Content-Length", "0"))
    assert content_length >= 0, f"negative Content-Length: {content_length}"
    assert resp.status != 206, (
        f"reversed range returned 206 with Content-Length={content_length}; "
        "should be 416"
    )


# Bug 2: Rename where new name equals current name returns 409.
# rename_item checks os.path.exists(new_path) before os.rename. When
# new_name == basename(filepath), new_path == filepath, which always exists,
# so the API rejects what should be a no-op.
@pytest.mark.xfail(
    strict=True,
    reason="bug: rename to identical name returns 409 Already exists (should be no-op)",
)
def test_rename_to_same_name_is_not_conflict(test_server, temp_dir):
    src = os.path.join(temp_dir, "file.txt")
    data = json.dumps({"path": src, "name": "file.txt"}).encode()
    req = urllib.request.Request(
        f"{test_server}/api/rename",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    assert json.loads(resp.read())["ok"] is True
    assert os.path.exists(src)


# Bug 3: Case-only rename blocked on case-insensitive filesystems.
# On macOS' default APFS, "file.txt" and "FILE.TXT" resolve to the same inode,
# so os.path.exists(new_path) returns True and rename_item rejects the request
# with 409. Users cannot change the case of a filename through the UI.
@pytest.mark.xfail(
    strict=True,
    reason="bug: case-only rename blocked by exists() check on case-insensitive FS",
)
def test_case_only_rename(test_server, temp_dir):
    if not _fs_is_case_insensitive(temp_dir):
        pytest.skip("filesystem is case-sensitive; bug not reachable here")
    src = os.path.join(temp_dir, "file.txt")
    data = json.dumps({"path": src, "name": "FILE.TXT"}).encode()
    req = urllib.request.Request(
        f"{test_server}/api/rename",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    assert json.loads(resp.read())["ok"] is True
    listing = json.loads(urllib.request.urlopen(
        f"{test_server}/api/ls?dir={urllib.parse.quote(temp_dir)}"
    ).read())
    names = [e["name"] for e in listing["entries"]]
    assert "FILE.TXT" in names
    assert "file.txt" not in names


# Bug 4: Broken symlinks silently skipped from /api/ls output.
# serve_listing calls os.stat (which follows links); dangling symlinks raise
# FileNotFoundError and the except clause drops the entry entirely. Users
# can't see or clean up dangling links through the UI.
@pytest.mark.xfail(
    strict=True,
    reason="bug: dangling symlinks filtered out of /api/ls (os.stat follows, then skips)",
)
def test_broken_symlink_appears_in_listing(test_server, temp_dir):
    broken = os.path.join(temp_dir, "dangling")
    os.symlink("/nonexistent_target_xyz", broken)
    assert os.path.islink(broken)
    url = f"{test_server}/api/ls?dir={urllib.parse.quote(temp_dir)}"
    data = json.loads(urllib.request.urlopen(url).read())
    names = [e["name"] for e in data["entries"]]
    assert "dangling" in names


# Bug 5: /api/ls on a file path returns 500.
# serve_listing only catches PermissionError and FileNotFoundError.
# Passing a regular file path raises NotADirectoryError from os.listdir,
# which propagates up as an unhandled 500. Expected a 4xx (e.g. 400).
@pytest.mark.xfail(
    strict=True,
    reason="bug: /api/ls on a file path returns 500 (NotADirectoryError unhandled)",
)
def test_ls_on_file_returns_client_error(test_server, temp_dir):
    path = os.path.join(temp_dir, "file.txt")
    url = f"{test_server}/api/ls?dir={urllib.parse.quote(path)}"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url)
    assert 400 <= exc_info.value.code < 500


# Bug 6: Malformed JSON POST body closes the connection without a response.
# do_POST calls json.loads unconditionally; JSONDecodeError is not caught, so
# the client sees RemoteDisconnected instead of a 4xx error.
@pytest.mark.xfail(
    strict=True,
    reason="bug: malformed JSON POST body raises unhandled JSONDecodeError (no HTTP response)",
)
def test_malformed_json_returns_400(test_server):
    data = b"this is not json {"
    req = urllib.request.Request(
        f"{test_server}/api/rename",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=3)
    except urllib.error.HTTPError as e:
        assert 400 <= e.code < 500
        return
    except (urllib.error.URLError, http.client.RemoteDisconnected) as e:
        pytest.fail(f"connection dropped without HTTP response: {e}")
    pytest.fail(f"malformed JSON produced status {resp.status}")


# --- Non-xfail tests: behaviors that are currently correct, kept as a guard ---

class TestSelfMoveGuard:
    """Moving a directory into itself must not succeed silently."""

    def test_move_dir_into_self_is_rejected(self, test_server, temp_dir):
        src = os.path.join(temp_dir, "subdir")
        data = json.dumps({"paths": [src], "dest": src}).encode()
        req = urllib.request.Request(
            f"{test_server}/api/move",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            assert e.code == 400
            assert os.path.isdir(src)
            return
        body = json.loads(resp.read())
        assert body.get("ok") is False
        assert os.path.isdir(src)


class TestCopyIntoDescendantGuard:
    """Copying a directory into its own descendant must not silently succeed."""

    def test_copy_dir_into_own_subdir_is_rejected(self, test_server, temp_dir):
        src = os.path.join(temp_dir, "subdir")
        with open(os.path.join(src, "a.txt"), "w") as f:
            f.write("x")
        nested = os.path.join(src, "inner")
        os.makedirs(nested)
        data = json.dumps({"paths": [src], "dest": nested}).encode()
        req = urllib.request.Request(
            f"{test_server}/api/copy",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            assert e.code == 400
            return
        body = json.loads(resp.read())
        assert body.get("ok") is False
