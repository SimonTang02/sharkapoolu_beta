"""Optional SQLite access over an authenticated SSH standard-input channel.

Without private connection configuration, connect() is ordinary sqlite3.
The SSH backend runs the SQLite engine beside its database on the host. It
never synchronizes or replaces a live database file and never retries writes.
"""

from __future__ import annotations

import argparse
import base64
from collections import deque
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

from private_paths import (
    DATABASE_BACKUP_DIR,
    DATABASE_CONNECTION_CONFIG,
    DATABASE_DIR,
    JOB_DATABASE,
)

MAX_MESSAGE_BYTES = 16 * 1024 * 1024
FETCH_BATCH = 64
ERROR_TYPES = {
    name: getattr(sqlite3, name)
    for name in (
        "Error", "DatabaseError", "DataError", "IntegrityError",
        "InterfaceError", "InternalError", "NotSupportedError",
        "OperationalError", "ProgrammingError",
    )
}


def _encode(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return {"$float": repr(value)}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$bytes"}:
            return base64.b64decode(value["$bytes"], validate=True)
        if set(value) == {"$float"}:
            return float(value["$float"])
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def _message(value: Any) -> bytes:
    result = json.dumps(_encode(value), ensure_ascii=True, allow_nan=False,
                        separators=(",", ":")).encode("ascii") + b"\n"
    if len(result) > MAX_MESSAGE_BYTES:
        raise sqlite3.OperationalError("Shared database message exceeds size limit")
    return result


def _database_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(sqlite3|sqlite|db)", value):
        raise ValueError("Database must be a filename with a SQLite extension")
    return value


def _validate_config(config: dict) -> dict:
    if config.get("mode") == "local":
        return {"mode": "local"}
    if config.get("mode") != "ssh":
        raise ValueError("Database connection mode must be local or ssh")
    host = config.get("host", "")
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", host):
        raise ValueError("Set a valid SSH host alias in the private connection config")
    for name in ("project_dir", "python"):
        if not isinstance(config.get(name), str) or not config[name].strip():
            raise ValueError(f"Missing connection setting: {name}")
        if any(char in config[name] for char in "\n\r\0"):
            raise ValueError(f"Invalid connection setting: {name}")
    private_dir = config.get("private_dir")
    if private_dir is not None and (
        not isinstance(private_dir, str) or not private_dir.strip()
        or any(char in private_dir for char in "\n\r\0")
    ):
        raise ValueError("Invalid connection setting: private_dir")
    timeout = config.get("request_timeout", 60)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300:
        raise ValueError("request_timeout must be between 1 and 300 seconds")
    return {**config, "request_timeout": timeout}


def _remote_path(value: str) -> str:
    if value == "~":
        return '"$HOME"'
    if value.startswith("~/"):
        return '"$HOME"/' + shlex.quote(value[2:])
    return shlex.quote(value)


def ssh_command(config: dict, database: str) -> list[str]:
    config = _validate_config(config)
    command = "cd " + _remote_path(config["project_dir"]) + " && exec "
    if config.get("private_dir"):
        command += "env " + shlex.quote("JOBBOT_PRIVATE_DIR=" + config["private_dir"]) + " "
    command += _remote_path(config["python"]) + " -m job_bot.shared_database serve --database "
    command += shlex.quote(_database_name(database))
    return [
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=10", "-o", "ConnectionAttempts=1",
        "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
        "-o", "LogLevel=ERROR", config["host"], command,
    ]


def connect(database: str | Path, *, timeout: float = 5.0):
    """Route private database connections through SSH when explicitly configured.

External fixture databases and :memory: retain normal SQLite behavior. An
invalid configuration or failed SSH connection raises; it never falls back
to a separate writable local database.
    """
    raw = str(database)
    path = Path(raw).expanduser().resolve()
    if raw == ":memory:" or path.parent != DATABASE_DIR.resolve():
        return sqlite3.connect(database, timeout=timeout)
    if not DATABASE_CONNECTION_CONFIG.exists():
        return sqlite3.connect(database, timeout=timeout)
    try:
        config = _validate_config(json.loads(DATABASE_CONNECTION_CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise sqlite3.OperationalError("Invalid private database connection configuration") from None
    if config["mode"] == "local":
        return sqlite3.connect(database, timeout=timeout)
    ensure_ssh_platform()
    return SSHConnection(ssh_command(config, path.name),
                         request_timeout=config["request_timeout"], timeout=timeout)


def ensure_ssh_platform() -> None:
    if os.name == "nt":
        raise sqlite3.OperationalError("SSH database RPC uses Unix pipes; use WSL on Windows. Writable local fallback is disabled.")


class SSHConnection:
    """The subset of sqlite3.Connection used by this repository."""

    def __init__(self, command: list[str], *, request_timeout: float = 60, timeout: float = 5):
        self.row_factory = None
        self.in_transaction = False
        self.total_changes = 0
        self._request_timeout = request_timeout
        self._closed = False
        self._thread_id = threading.get_ident()
        self._buffer = bytearray()
        self._templates = sqlite3.connect(":memory:")
        try:
            self._process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             bufsize=0)
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            self._request({"op": "open", "timeout": min(timeout, 30)})
        except (OSError, sqlite3.Error):
            self._abort()
            raise sqlite3.OperationalError(
                "Cannot open shared database. Check SSH host key, key authentication, "
                "remote project, Python, and database. Local fallback is disabled."
            ) from None

    def _abort(self) -> None:
        self._closed = True
        process = getattr(self, "_process", None)
        if process is not None:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    stream.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        self._templates.close()

    def _request(self, request: dict) -> dict:
        if self._closed:
            raise sqlite3.ProgrammingError("Shared database connection is closed")
        if threading.get_ident() != self._thread_id:
            raise sqlite3.ProgrammingError("Shared database connections must stay on their creating thread")
        packet = _message(request)
        deadline = time.monotonic() + self._request_timeout
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self._process.stdin, selectors.EVENT_WRITE)
                offset = 0
                while offset < len(packet):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError
                    offset += os.write(self._process.stdin.fileno(), packet[offset:])
                selector.unregister(self._process.stdin)
                selector.register(self._process.stdout, selectors.EVENT_READ)
                while b"\n" not in self._buffer:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError
                    chunk = os.read(self._process.stdout.fileno(), 65536)
                    if not chunk:
                        raise EOFError
                    self._buffer.extend(chunk)
                    if len(self._buffer) > MAX_MESSAGE_BYTES:
                        raise ValueError
            line, _, rest = self._buffer.partition(b"\n")
            self._buffer = bytearray(rest)
            response = _decode(json.loads(line))
            self.in_transaction = response.get("in_transaction", self.in_transaction)
            self.total_changes = response.get("total_changes", self.total_changes)
        except (OSError, EOFError, TimeoutError, ValueError):
            self._abort()
            raise sqlite3.OperationalError(
                "Shared database channel failed. If a write or commit was in flight, "
                "its outcome is unknown; check stored state before retrying."
            ) from None
        if "error" in response:
            error_type = ERROR_TYPES.get(response["error"], sqlite3.DatabaseError)
            raise error_type("Shared database rejected the operation (" + response["error"] + ")")
        return response

    def cursor(self):
        return SSHCursor(self)

    def execute(self, sql: str, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql: str, parameters):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, sql: str):
        return self.cursor().executescript(sql)

    def commit(self) -> None:
        self._request({"op": "commit"})

    def rollback(self) -> None:
        self._request({"op": "rollback"})

    def backup(self, target, *, pages: int = -1, progress=None,
               name: str = "main", sleep: float = 0.250) -> None:
        if name != "main" or self.in_transaction:
            raise sqlite3.ProgrammingError("Backup requires the main database and no active transaction")
        DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        response = self._request({"op": "backup_start"})
        temporary = None
        try:
            descriptor, filename = tempfile.mkstemp(dir=DATABASE_BACKUP_DIR, suffix=".sqlite3")
            temporary = Path(filename)
            with os.fdopen(descriptor, "wb") as output:
                while not response["done"]:
                    response = self._request({"op": "backup_read"})
                    output.write(response["chunk"])
            source = sqlite3.connect(temporary)
            try:
                if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise sqlite3.DatabaseError("Shared database backup integrity check failed")
                source.backup(target, pages=pages, progress=progress, sleep=sleep)
            finally:
                source.close()
        finally:
            try:
                if not self._closed:
                    self._request({"op": "backup_close"})
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def close(self) -> None:
        if not self._closed:
            try:
                self._request({"op": "close"})
            finally:
                self._abort()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            try:
                self.commit()
            except sqlite3.Error:
                if not self._closed:
                    self.rollback()
                raise
        else:
            self.rollback()
        return False

    def __del__(self):
        if not getattr(self, "_closed", True):
            self._abort()


class SSHCursor:
    def __init__(self, connection: SSHConnection):
        self.connection = connection
        self.row_factory = connection.row_factory
        self.description = None
        self.lastrowid = None
        self.rowcount = -1
        self.arraysize = 1
        self._id = None
        self._rows = deque()
        self._template = None
        self._closed = False

    def _release(self) -> None:
        if self._id is not None and not self.connection._closed:
            self.connection._request({"op": "cursor_close", "cursor": self._id})
        self._id = None
        if self._template is not None:
            self._template.close()
            self._template = None

    def _execute(self, op: str, sql: str, parameters=None):
        if self._closed:
            raise sqlite3.ProgrammingError("Shared database cursor is closed")
        self._release()
        request = {"op": op, "sql": sql}
        if parameters is not None:
            request["parameters"] = parameters
        response = self.connection._request(request)
        self.description = tuple(tuple(item) for item in response["description"]) if response["description"] else None
        self.lastrowid = response["lastrowid"]
        self.rowcount = response["rowcount"]
        self._id = response.get("cursor")
        self._rows = deque(response["rows"])
        if self.description and self.row_factory is sqlite3.Row:
            # Native sqlite3.Row preserves names, duplicate columns, indexing,
            # slicing, keys(), and dict(row) without reimplementing its rules.
            columns = ["NULL AS \"" + item[0].replace('"', '""') + "\"" for item in self.description]
            self._template = self.connection._templates.execute("SELECT " + ",".join(columns))
        return self

    def execute(self, sql: str, parameters=()):
        return self._execute("execute", sql, parameters)

    def executemany(self, sql: str, parameters):
        return self._execute("executemany", sql, list(parameters))

    def executescript(self, sql: str):
        return self._execute("executescript", sql)

    def fetchone(self):
        if self._closed:
            raise sqlite3.ProgrammingError("Shared database cursor is closed")
        if not self._rows and self._id is not None:
            response = self.connection._request({"op": "fetch", "cursor": self._id})
            self._id = response.get("cursor")
            self._rows.extend(response["rows"])
            self.rowcount = response["rowcount"]
        if not self._rows:
            return None
        values = tuple(self._rows.popleft())
        if self.row_factory is sqlite3.Row:
            return sqlite3.Row(self._template, values)
        return self.row_factory(self, values) if self.row_factory else values

    def fetchmany(self, size=None):
        result = []
        for _ in range(self.arraysize if size is None else size):
            row = self.fetchone()
            if row is None:
                break
            result.append(row)
        return result

    def fetchall(self):
        return list(self)

    def close(self) -> None:
        self._release()
        self._rows.clear()
        self._closed = True

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __del__(self):
        try:
            self._release()
        except (OSError, sqlite3.Error):
            pass


def serve(database: str, *, idle_timeout: float = 900) -> None:
    """One SSH session owns one SQLite connection and transaction scope."""
    path = DATABASE_DIR / _database_name(database)
    if path.resolve().parent != DATABASE_DIR.resolve():
        raise ValueError("Database must remain below the canonical private database directory")
    conn = None
    cursors = {}
    cursor_sequence = 0
    snapshot = None
    snapshot_path = None

    def close_snapshot():
        nonlocal snapshot, snapshot_path
        if snapshot is not None:
            snapshot.close()
            snapshot = None
        if snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)
            snapshot_path = None

    try:
        while True:
            # A dropped or abandoned client must eventually release write locks.
            with selectors.DefaultSelector() as selector:
                selector.register(sys.stdin.buffer, selectors.EVENT_READ)
                if not selector.select(idle_timeout):
                    break
            line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
                break
            stop = False
            try:
                request = _decode(json.loads(line))
                op = request["op"]
                response = {}
                if op == "open" and conn is None:
                    # mode=rw prevents accidental creation of a second database.
                    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True,
                                           timeout=request.get("timeout", 5))
                elif conn is None:
                    raise sqlite3.ProgrammingError
                elif op in {"execute", "executemany", "executescript"}:
                    cursor = conn.cursor()
                    try:
                        if op == "executescript":
                            cursor.executescript(request["sql"])
                        else:
                            getattr(cursor, op)(request["sql"], request.get("parameters", []))
                        rows = cursor.fetchmany(FETCH_BATCH) if cursor.description else []
                        response = {"description": cursor.description, "rows": rows,
                                    "lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}
                        if len(rows) == FETCH_BATCH:
                            cursor_sequence += 1
                            cursors[cursor_sequence] = cursor
                            response["cursor"] = cursor_sequence
                        else:
                            cursor.close()
                    except BaseException:
                        cursor.close()
                        raise
                elif op == "fetch":
                    cursor_id = request["cursor"]
                    cursor = cursors[cursor_id]
                    rows = cursor.fetchmany(FETCH_BATCH)
                    response = {"rows": rows, "rowcount": cursor.rowcount}
                    if len(rows) == FETCH_BATCH:
                        response["cursor"] = cursor_id
                    else:
                        cursors.pop(cursor_id).close()
                elif op == "cursor_close":
                    cursor = cursors.pop(request["cursor"], None)
                    if cursor is not None:
                        cursor.close()
                elif op == "commit":
                    conn.commit()
                elif op == "rollback":
                    conn.rollback()
                elif op == "backup_start":
                    if conn.in_transaction:
                        raise sqlite3.ProgrammingError
                    close_snapshot()
                    DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                    descriptor, filename = tempfile.mkstemp(dir=DATABASE_BACKUP_DIR, suffix=".sqlite3")
                    os.close(descriptor)
                    snapshot_path = Path(filename)
                    destination = sqlite3.connect(snapshot_path)
                    try:
                        deadline = time.monotonic() + 45
                        def progress(status, remaining, total):
                            if time.monotonic() > deadline:
                                raise sqlite3.OperationalError
                        conn.backup(destination, pages=256, progress=progress, sleep=0.05)
                    finally:
                        destination.close()
                    snapshot = snapshot_path.open("rb")
                    response = {"done": False}
                elif op == "backup_read":
                    if snapshot is None:
                        raise sqlite3.ProgrammingError
                    chunk = snapshot.read(65536)
                    response = {"chunk": chunk, "done": not chunk}
                    if not chunk:
                        close_snapshot()
                elif op == "backup_close":
                    close_snapshot()
                elif op == "close":
                    stop = True
                else:
                    raise sqlite3.ProgrammingError
            except (sqlite3.Error, KeyError, ValueError, TypeError):
                # Error text may embed SQL, bound values, or private paths.
                error_name = sys.exc_info()[0].__name__
                response = {"error": error_name if error_name in ERROR_TYPES else "ProgrammingError"}
            if conn is not None:
                response.update(in_transaction=conn.in_transaction, total_changes=conn.total_changes)
            try:
                packet = _message(response)
            except sqlite3.Error:
                packet = _message({"error": "OperationalError"})
            sys.stdout.buffer.write(packet)
            sys.stdout.buffer.flush()
            if stop:
                break
    finally:
        close_snapshot()
        for cursor in cursors.values():
            cursor.close()
        if conn is not None:
            conn.close()  # Uncommitted work is rolled back on disconnect.


def _write_config(config: dict) -> None:
    DATABASE_CONNECTION_CONFIG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=DATABASE_CONNECTION_CONFIG.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(config, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, DATABASE_CONNECTION_CONFIG)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve", help="Private protocol endpoint launched by SSH")
    server.add_argument("--database", default=JOB_DATABASE.name)
    server.add_argument("--idle-timeout", type=float, default=900)
    setup = commands.add_parser("configure", help="Preview or save this client's connection settings")
    setup.add_argument("--host", required=True, help="Existing SSH alias of the database host")
    setup.add_argument("--project-dir", required=True, help="Project directory on the database host")
    setup.add_argument("--python", default=".venv/bin/python")
    setup.add_argument("--private-dir", help="Host private root when JOBBOT_PRIVATE_DIR is used")
    setup.add_argument("--request-timeout", type=float, default=60)
    setup.add_argument("--apply", action="store_true")
    commands.add_parser("check", help="Check the configured connection without schema or data writes")
    watch = commands.add_parser("watch", help="Report committed changes without printing database contents")
    watch.add_argument("--interval", type=float, default=1.0)
    prepare = commands.add_parser("prepare-host", help="Back up the host database and enable WAL")
    prepare.add_argument("--database", default=JOB_DATABASE.name)
    prepare.add_argument("--apply", action="store_true")
    local = commands.add_parser("local", help="Preview or explicitly restore local connection mode")
    local.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve(args.database, idle_timeout=args.idle_timeout)
        elif args.command == "configure":
            config = {"mode": "ssh", "host": args.host, "project_dir": args.project_dir,
                      "python": args.python, "request_timeout": args.request_timeout}
            if args.private_dir:
                config["private_dir"] = args.private_dir
            config = _validate_config(config)
            print("Mode: SSH; private databases use the host's matching filenames.")
            print("No database, credentials, profiles, or browser files will be copied.")
            if args.apply:
                _write_config(config)
                print("Saved private connection configuration. Run check before using workflows.")
            else:
                print("Preview only. Add --apply to save this client's configuration.")
        elif args.command in {"check", "watch"}:
            if not JOB_DATABASE.is_file():
                config = json.loads(DATABASE_CONNECTION_CONFIG.read_text(encoding="utf-8")) if DATABASE_CONNECTION_CONFIG.exists() else {"mode": "local"}
                if _validate_config(config)["mode"] == "local":
                    raise ValueError("Initialize the local database before checking it")
            if args.command == "watch" and not 0.2 <= args.interval <= 60:
                raise ValueError("Watch interval must be between 0.2 and 60 seconds")
            conn = connect(JOB_DATABASE)
            try:
                conn.execute("SELECT 1").fetchone()
                version = conn.execute("PRAGMA data_version").fetchone()[0]
                print(f"Database connection OK; data_version={version}")
                if args.command == "watch":
                    print("Watching committed changes; press Ctrl+C to stop.", flush=True)
                    try:
                        while True:
                            time.sleep(args.interval)
                            current = conn.execute("PRAGMA data_version").fetchone()[0]
                            if current != version:
                                print("Database updated at " + datetime.now(timezone.utc).isoformat(), flush=True)
                                version = current
                    except KeyboardInterrupt:
                        pass
            finally:
                conn.close()
        elif args.command == "local":
            if args.apply:
                _write_config({"mode": "local"})
                print("Local connection mode saved. Existing local files have not been refreshed.")
            else:
                print("Preview: restore local connections. Add --apply only on the database host,")
                print("or after separately restoring and checking a current database backup.")
        elif args.command == "prepare-host":
            path = DATABASE_DIR / _database_name(args.database)
            if not path.is_file():
                raise ValueError("Initialize the host database before preparing it")
            if DATABASE_CONNECTION_CONFIG.exists():
                config = _validate_config(json.loads(DATABASE_CONNECTION_CONFIG.read_text(encoding="utf-8")))
                if config["mode"] != "local":
                    raise ValueError("prepare-host requires local connection mode")
            print("Plan: create a private SQLite backup, check integrity, and enable WAL.")
            if not args.apply:
                print("Preview only. Add --apply to prepare the database host.")
                return
            DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
            backup = DATABASE_BACKUP_DIR / f"{path.stem}.{stamp}.sqlite3"
            descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            source = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=10)
            destination = sqlite3.connect(backup)
            try:
                deadline = time.monotonic() + 60
                def progress(status, remaining, total):
                    if time.monotonic() > deadline:
                        raise TimeoutError("Host backup timed out; retry when database activity is lower")
                source.backup(destination, pages=256, progress=progress, sleep=0.05)
                if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Backup integrity check failed")
                mode = source.execute("PRAGMA journal_mode=WAL").fetchone()[0]
                if mode != "wal":
                    raise ValueError("WAL could not be enabled; stop active workflows and retry")
            finally:
                destination.close()
                source.close()
            print(f"Host ready; backup saved under database/backups/; journal_mode={mode}")
    except (OSError, ValueError, TypeError, AttributeError, TimeoutError, sqlite3.Error) as exc:
        if args.command == "serve":
            raise SystemExit(1) from None
        # Deliberately omit exception text that could include private values.
        print(f"Database operation failed ({type(exc).__name__}). Check local paths, "
              "SSH setup, and connection settings.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
