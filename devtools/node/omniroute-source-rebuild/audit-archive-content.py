"""Read-only independent tar-to-Git-blob audit; no source extraction or logging."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

COMMIT = "ad6f33f66bda34eba98645d3bfdabbde294bc843"
TREE = "b2f3332f645ad60de52f12a4a484eb288693f0ea"
OPTIONS = ["--no-replace-objects", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-c", "tar.umask=0002"]

def audit(root):
    env = dict(os.environ, GIT_NO_REPLACE_OBJECTS="1")
    def git(*args, data=None):
        return subprocess.check_output(["git", *OPTIONS, *args], cwd=root, env=env, input=data, stderr=subprocess.DEVNULL)
    assert git("rev-parse", COMMIT + "^{tree}").decode().strip() == TREE
    entries = {}
    directories = set()
    for line in git("ls-tree", "-rz", "--full-tree", COMMIT).split(b"\0"):
        if not line:
            continue
        metadata, path = line.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split(" ")
        assert kind == "blob" and mode in ("100644", "100755")
        name = path.decode("utf-8")
        assert name not in entries
        entries[name] = (mode, blob)
        parts = name.split("/")
        directories.update("/".join(parts[:index]) for index in range(1, len(parts)))
    attrs = git("check-attr", "--source=" + COMMIT, "-z", "--stdin", "export-ignore", "export-subst", data=b"\0".join(name.encode() for name in entries) + b"\0").split(b"\0")
    assert all(attrs[index] == b"unspecified" for index in range(2, len(attrs) - 1, 3))
    archive = subprocess.Popen(["git", *OPTIONS, "archive", "--format=tar", COMMIT], cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    digest = hashlib.sha256()
    class Reader:
        count = 0
        def read(self, size=-1):
            chunk = archive.stdout.read(size)
            digest.update(chunk)
            self.count += len(chunk)
            return chunk
    reader = Reader()
    checked = {}
    try:
        with tarfile.open(fileobj=reader, mode="r|") as stream:
            for member in stream:
                if member.isdir():
                    assert member.name.rstrip("/") in directories and member.mode == 0o775
                    continue
                assert member.isfile() and member.name in entries and member.name not in checked
                mode, oid = entries[member.name]
                assert member.mode == (0o775 if mode == "100755" else 0o664)
                blob = hashlib.sha1(("blob " + str(member.size) + "\0").encode())
                raw = hashlib.sha256()
                content = stream.extractfile(member)
                while chunk := content.read(1024 * 1024):
                    blob.update(chunk)
                    raw.update(chunk)
                assert blob.hexdigest() == oid
                checked[member.name] = (mode, raw.hexdigest())
        while reader.read(1024 * 1024):
            pass
        assert archive.wait(timeout=30) == 0
        assert checked.keys() == entries.keys()
        manifest = [[name, *checked[name]] for name in sorted(checked)]
        return {"commit": COMMIT, "tree": TREE, "trackedRawBlobMatches": len(checked), "exportAttributesActive": 0, "archiveBytes": reader.count, "canonicalArchiveSha256": digest.hexdigest(), "rawContentManifestSha256": hashlib.sha256(json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(), "sourceExtracted": False}
    finally:
        if archive.poll() is None:
            archive.kill()
            archive.wait(timeout=10)
        archive.stdout.close()

if __name__ == "__main__":
    assert len(sys.argv) == 2
    print(json.dumps(audit(Path(sys.argv[1])), separators=(",", ":")))
