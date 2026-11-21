"""Copy NetraAttend's MongoDB data into OfficeEye's database - one database for
both apps, on the same Atlas cluster.

    py -3.12 tools/merge_netra_db.py              copy (again): the copy becomes exactly the source
    py -3.12 tools/merge_netra_db.py --dry-run    only say what it would do

The source database (netraattend) is only read - never changed or deleted; it
stays as a backup. Every collection keeps its name, its documents (same _id)
and its indexes (the photos' expiry too), so registered faces (face_samples),
employees, attendance, leaves and settings come over as they are: nobody has
to register their face again. OfficeEye's own collections (cameras,
detections, camera_uptime_*) have other names and are never touched; a name
both would use stops the copy.

Run it once now, and once more at the switch-over (DEPLOY_VPS.md): until then
the NetraAttend on the office PC still writes to netraattend.
"""

import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from officeeye.models import mongo  # noqa: E402 - OfficeEye's connection (MONGO_URI in .env)

SOURCE = "netraattend"
OFFICEEYE = {"cameras", "detections", "camera_uptime_hourly", "camera_uptime_daily", "sync_state",
             "selftest"}
BATCH = 200


def copy_indexes(src, dst, dry):
    for name, info in src.index_information().items():
        if name == "_id_":
            continue
        opts = {k: v for k, v in info.items() if k not in ("key", "v", "ns")}
        if not dry:
            dst.create_index(info["key"], name=name, **opts)


def _write(dst, ops):
    """A record the copy already has under another _id (one attendance row a
    person a day) stays as the copy has it - the live one."""
    from pymongo.errors import BulkWriteError
    try:
        dst.bulk_write(ops, ordered=False)
    except BulkWriteError as exc:
        if any(e.get("code") != 11000 for e in exc.details.get("writeErrors", [])):
            raise


def _photo_marks(coll):
    """{_id: (saved at, size)} of every photo, without the pictures themselves:
    an OUT photo is replaced during the day under the same name."""
    return {d["_id"]: (d.get("c"), d.get("n")) for d in coll.aggregate(
        [{"$project": {"c": "$created_at", "n": {"$binarySize": "$data"}}}])}


def copy_photos(src, dst, dry, catch_up):
    """Photos (most of the data): only the new or replaced ones travel."""
    from pymongo import ReplaceOne
    have, want = _photo_marks(dst), _photo_marks(src)
    if catch_up:
        todo = [i for i in want if i not in have]
    else:
        todo = [i for i, m in want.items() if have.get(i) != m]
    for k in range(0, len(todo), BATCH):
        docs = list(src.find({"_id": {"$in": todo[k:k + BATCH]}}))
        if docs and not dry:
            _write(dst, [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs])
    gone = [] if (dry or catch_up) else [i for i in have if i not in want]
    if gone:
        dst.delete_many({"_id": {"$in": gone}})
    return len(todo), len(gone)


def copy_docs(src, dst, dry, catch_up=False):
    """catch_up: only add what is missing - never replace or remove (after the
    switch the copy is the live data, it must not be put back)."""
    from pymongo import InsertOne, ReplaceOne
    if src.name == "photos":
        return copy_photos(src, dst, dry, catch_up)
    have = set(dst.distinct("_id")) if catch_up else set()
    ids, ops, done = set(), [], 0
    for doc in src.find().batch_size(BATCH):
        if catch_up:
            if doc["_id"] not in have:
                ops.append(InsertOne(doc))
            if len(ops) >= BATCH:
                if not dry:
                    _write(dst, ops)
                done += len(ops)
                ops = []
            continue
        ids.add(doc["_id"])
        ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        if len(ops) >= BATCH:
            if not dry:
                dst.bulk_write(ops, ordered=False)
            done += len(ops)
            ops = []
    if ops and not dry:
        _write(dst, ops)
    done += len(ops)
    # deleted in the source since the last copy: gone from the copy too
    # (never in a catch-up: there the copy already has newer, live data)
    gone = [] if (dry or catch_up) else [i for i in dst.distinct("_id") if i not in ids]
    if gone:
        dst.delete_many({"_id": {"$in": gone}})
    return done, len(gone)


def faces_hash(coll):
    h = hashlib.sha256()
    for doc in coll.find({}, {"embedding": 1, "emp_id": 1}).sort("_id", 1):
        h.update(str(doc["_id"]).encode())
        h.update(str(doc.get("emp_id")).encode())
        h.update(bytes(doc.get("embedding") or b""))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=SOURCE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--catch-up", action="store_true",
                    help="after the switch: only add what the source has and the copy lacks")
    a = ap.parse_args()
    target = mongo.get_db()
    client = target.client
    if a.source not in client.list_database_names():
        sys.exit("no database %r on this cluster" % a.source)
    src_db = client[a.source]
    if target.name == a.source:
        sys.exit("MONGO_URI points at %r itself - nothing to copy" % a.source)
    names = sorted(src_db.list_collection_names())
    clash = sorted(set(names) & OFFICEEYE)
    if clash:
        sys.exit("stopped: OfficeEye already uses %s - nothing was copied" % ", ".join(clash))
    print("%s -> %s: %d collections%s%s" % (a.source, target.name, len(names),
                                           " (catch-up: only missing ones added)" if a.catch_up else "",
                                           " (dry run)" if a.dry_run else ""))
    t0 = time.time()
    for name in names:
        src, dst = src_db[name], target[name]
        copy_indexes(src, dst, a.dry_run)
        n, removed = copy_docs(src, dst, a.dry_run, a.catch_up)
        have, want = dst.count_documents({}), src.count_documents({})
        note = "" if a.catch_up or have == want else "  (DIFFERENT - run again)"
        print("  %-14s %6d in %s, %5d copied, %6d in %s%s%s" % (
            name, want, a.source, n, have, target.name, note,
            "  (%d removed: gone from the source)" % removed if removed else ""), flush=True)
    if not a.dry_run and not a.catch_up and "face_samples" in names:
        same = faces_hash(src_db.face_samples) == faces_hash(target.face_samples)
        print("registered faces identical: %s" % ("yes" if same else "NO - run again"))
    print("done in %.0f s; %s was only read" % (time.time() - t0, a.source))


if __name__ == "__main__":
    main()
