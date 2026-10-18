"""The key worker (web/noodle-kdf-worker.js) and the Argon2 it runs
(web/vendor/hash-wasm-*) are loaded by new Worker()/importScripts, which
Subresource Integrity cannot cover. So they are pinned by a sha384 hard-coded in
web/noodle-kdf.js -- which IS SRI-pinned on the vote page -- and run from a Blob
of exactly the verified bytes (noodle ARCHITECTURE.md 21m). This test keeps those
hashes honest: change the worker or the vendor and forget to update
noodle-kdf.js, and the derive would fail closed in every browser -- so fail here,
loudly, before deploy, instead."""
import base64
import hashlib
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def _sha384(data: bytes) -> str:
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def _src() -> str:
    return (WEB / "noodle-kdf.js").read_text(encoding="utf-8")


def _const(src: str, name: str) -> str:
    m = re.search(rf"var {name} = '([^']+)';", src)
    assert m, f"noodle-kdf.js must define {name}"
    return m.group(1)


def _pin(src: str, varname: str) -> str:
    m = re.search(rf"NDK_PIN\[{varname}\] = '(sha384-[A-Za-z0-9+/=]+)';", src)
    assert m, f"noodle-kdf.js must pin {varname}"
    return m.group(1)


def test_kdf_pins_match_the_served_files():
    src = _src()
    for varname in ("NDK_WORKER_SRC", "NDK_VENDOR_SRC"):
        path = _const(src, varname)
        f = WEB / path.lstrip("/")
        assert f.is_file(), f"{path} does not resolve to a served file"
        assert _pin(src, varname) == _sha384(f.read_bytes()), (
            f"{path}: the sha384 in noodle-kdf.js != the file -- "
            "run openssl dgst -sha384 -binary <file> | openssl base64 and update NDK_PIN")


def test_worker_skips_importscripts_when_vendor_is_already_present():
    """The pinned Blob prepends the vendor, so the worker must NOT re-fetch it
    (that would be an unpinned load). It loads it only when absent (standalone)."""
    w = (WEB / "noodle-kdf-worker.js").read_text(encoding="utf-8")
    assert "typeof self.hashwasm === 'undefined'" in w
    assert "importScripts(" in w


def test_kdf_runs_the_worker_from_a_verified_blob_and_fails_closed():
    src = _src()
    assert "URL.createObjectURL(new Blob(" in src, "worker must run from a Blob of verified bytes"
    assert "integrity mismatch" in src, "a hash mismatch must be a hard, non-retried failure"


def test_vote_and_rekey_opt_into_pinning():
    assert "pin: true" in (WEB / "noodle-vote.js").read_text(encoding="utf-8")
    assert "pin: true" in (WEB / "noodle-rekey.js").read_text(encoding="utf-8")
