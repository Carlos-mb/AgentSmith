"""Controlled Linux prerequisites probe, NOT the Agent Smith sandbox.

Run with Python 3.10 as your normal user. Only Python's standard library is used.
Each restriction is applied in a disposable child, never to the parent or shell.
Files belong to a temporary directory; no project files or secrets are opened.

Scope: Landlock read/write allowlists, an empty allowlist, and creation of a
private network namespace with an inactive loopback interface. The network
probe only attempts local IPv4 TCP/UDP traffic. It does not contact the Internet.

Not covered: a complete filesystem policy (Landlock does not control every
metadata operation), imports, builtins, inherited descriptors, privilege removal,
RAM/time limits, Python execution, MCP integration or evaluation compatibility.

API references:
https://www.kernel.org/doc/html/v6.12/userspace-api/landlock.html
https://raw.githubusercontent.com/torvalds/linux/v6.12/include/uapi/linux/landlock.h
https://raw.githubusercontent.com/torvalds/linux/v6.12/arch/x86/entry/syscalls/syscall_64.tbl
https://man7.org/linux/man-pages/man2/unshare.2.html
"""

import ctypes
import errno
import json
import os
import platform
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


# Linux x86-64 syscall numbers. Reject other architectures before using them.
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38
CLONE_NEWUSER = 0x10000000
CLONE_NEWNET = 0x40000000

# ABI 3 filesystem rights are bits 0 through 14, including TRUNCATE.
HANDLED_FS = (1 << 15) - 1
# Allow ordinary file/directory operations, but not execution or special files.
ALLOWED_FS = sum(1 << bit for bit in (1, 2, 3, 4, 5, 7, 8, 12, 13, 14))


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _pack_ = 1  # This Linux ABI structure has no trailing padding.
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def check_result(result: int, operation: str) -> int:
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, f"{operation}: {os.strerror(error)}")
    return result


def load_libc():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    libc.syscall.argtypes = [ctypes.c_long]  # The remaining arguments are variadic.
    libc.prctl.restype = ctypes.c_int
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.unshare.restype = ctypes.c_int
    libc.unshare.argtypes = [ctypes.c_int]
    return libc


def apply_landlock(allowed_directories: list[Path]) -> int:
    """Install a deliberately limited filesystem policy in this child only."""
    libc = load_libc()
    abi = check_result(
        libc.syscall(
            SYS_LANDLOCK_CREATE_RULESET,
            ctypes.c_void_p(),
            ctypes.c_size_t(0),
            ctypes.c_uint(LANDLOCK_CREATE_RULESET_VERSION),
        ),
        "consultar Landlock ABI",
    )
    require(abi >= 3, f"Esta prueba necesita Landlock ABI >= 3; disponible: {abi}")

    attributes = RulesetAttr(HANDLED_FS)
    ruleset_fd = check_result(
        libc.syscall(
            SYS_LANDLOCK_CREATE_RULESET,
            ctypes.byref(attributes),
            ctypes.c_size_t(ctypes.sizeof(attributes)),
            ctypes.c_uint(0),
        ),
        "crear reglas Landlock",
    )
    try:
        for directory in allowed_directories:
            directory_fd = os.open(directory, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathBeneathAttr(ALLOWED_FS, directory_fd)
                check_result(
                    libc.syscall(
                        SYS_LANDLOCK_ADD_RULE,
                        ctypes.c_int(ruleset_fd),
                        ctypes.c_int(LANDLOCK_RULE_PATH_BENEATH),
                        ctypes.byref(rule),
                        ctypes.c_uint(0),
                    ),
                    "autorizar directorio temporal",
                )
            finally:
                os.close(directory_fd)

        check_result(libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0), "no_new_privs")
        check_result(
            libc.syscall(
                SYS_LANDLOCK_RESTRICT_SELF,
                ctypes.c_int(ruleset_fd),
                ctypes.c_uint(0),
            ),
            "aplicar Landlock",
        )
    finally:
        os.close(ruleset_fd)
    return abi


def must_be_denied(description, operation) -> None:
    try:
        operation()
    except PermissionError as error:
        require(error.errno in (errno.EACCES, errno.EPERM), str(error))
    else:
        raise RuntimeError(f"No se bloqueo: {description}")


def check_files(root: Path, empty: bool) -> str:
    allowed = root / "allowed"
    inside = allowed / "value.txt"
    outside = root / "outside" / "value.txt"
    link_inside = allowed / "link_inside"
    link_outside = allowed / "link_outside"

    # Establish that denied reads really worked before applying our restrictions.
    require(inside.read_text(encoding="utf-8") == "inside", "Fallo de preparacion")
    require(outside.read_text(encoding="utf-8") == "outside", "Fallo de preparacion")
    require(link_outside.read_text(encoding="utf-8") == "outside", "Enlace invalido")
    outside.write_text("outside", encoding="utf-8")
    abi = apply_landlock([] if empty else [allowed])

    if empty:
        must_be_denied("leer dentro con []", lambda: inside.read_bytes())
        must_be_denied("listar dentro con []", lambda: os.listdir(allowed))
        must_be_denied("escribir dentro con []", lambda: inside.write_bytes(b"changed"))
    else:
        inside.write_text("updated", encoding="utf-8")
        require(inside.read_text(encoding="utf-8") == "updated", "Lectura permitida fallo")
        require(link_inside.read_text(encoding="utf-8") == "updated", "Enlace interno fallo")
        require("value.txt" in os.listdir(allowed), "Listado permitido fallo")
        (allowed / "new.txt").write_text("new", encoding="utf-8")

    must_be_denied("leer fuera", lambda: outside.read_bytes())
    must_be_denied("escribir fuera", lambda: outside.write_bytes(b"changed"))
    must_be_denied("truncar fuera", lambda: os.truncate(outside, 0))
    must_be_denied("listar fuera", lambda: os.listdir(outside.parent))
    must_be_denied("enlace hacia fuera", lambda: link_outside.read_bytes())
    must_be_denied("crear fuera", lambda: (outside.parent / "new.txt").write_bytes(b"new"))
    return f"ABI {abi}; casos de lectura/escritura comprobados"


def check_network() -> str:
    import fcntl

    libc = load_libc()
    previous_net = os.readlink("/proc/self/ns/net")
    previous_user = os.readlink("/proc/self/ns/user")
    check_result(libc.unshare(CLONE_NEWUSER | CLONE_NEWNET), "unshare usuario + red")
    require(os.readlink("/proc/self/ns/net") != previous_net, "No cambio el namespace de red")
    require(os.readlink("/proc/self/ns/user") != previous_user, "No cambio el namespace de usuario")
    require({name for _, name in socket.if_nameindex()} == {"lo"}, "Interfaces inesperadas")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        # SIOCGIFFLAGS reads the loopback flags; IFF_UP is bit zero.
        request = struct.pack("256s", b"lo")
        reply = fcntl.ioctl(udp.fileno(), 0x8913, request)
        flags = struct.unpack_from("H", reply, 16)[0]
        require(not flags & 1, "Loopback esta activo")
        try:
            udp.sendto(b"probe", ("127.0.0.1", 9))
        except OSError as error:
            require(error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH), str(error))
        else:
            raise RuntimeError("UDP local se envio pese al aislamiento esperado")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
        tcp.settimeout(1)
        try:
            tcp.connect(("127.0.0.1", 9))
        except OSError as error:
            require(error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH), str(error))
        else:
            raise RuntimeError("TCP local conecto pese al aislamiento esperado")
    return "namespace distinto; solo lo inactivo; TCP/UDP IPv4 local sin ruta"


def child(mode: str, root: Path) -> int:
    try:
        if mode == "files":
            detail = check_files(root, empty=False)
        elif mode == "empty":
            detail = check_files(root, empty=True)
        elif mode == "network":
            detail = check_network()
        else:
            raise ValueError(f"Modo desconocido: {mode}")
    except Exception as error:
        print(json.dumps({"ok": False, "detail": f"{type(error).__name__}: {error}"}), flush=True)
        return 1
    print(json.dumps({"ok": True, "detail": detail}), flush=True)
    return 0


def main() -> int:
    require(sys.platform == "linux", "Esta prueba requiere Linux")
    require(platform.machine() == "x86_64" and ctypes.sizeof(ctypes.c_void_p) == 8,
            "Esta prueba esta preparada solo para Linux x86-64 de 64 bits")
    require(os.geteuid() != 0, "Ejecuta como usuario normal, sin sudo ni root")

    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        return child(sys.argv[2], Path(sys.argv[3]))
    require(len(sys.argv) == 1, "No se necesitan argumentos")

    print(f"Python: {platform.python_version()}")
    print(f"Sistema: Linux {platform.release()} {platform.machine()}")
    print("Prueba de prerrequisitos: NO es una certificacion del sandbox.", flush=True)
    original_net = os.readlink("/proc/self/ns/net")
    passed = 0
    script = str(Path(__file__).resolve())

    for mode, label in (
        ("files", "LANDLOCK_RUTAS"),
        ("empty", "LANDLOCK_LISTA_VACIA"),
        ("network", "NAMESPACE_RED"),
    ):
        with tempfile.TemporaryDirectory(prefix="agentsmith-prereq-") as folder:
            root = Path(folder)
            (root / "allowed").mkdir()
            (root / "outside").mkdir()
            (root / "allowed" / "value.txt").write_text("inside", encoding="utf-8")
            (root / "outside" / "value.txt").write_text("outside", encoding="utf-8")
            (root / "allowed" / "link_inside").symlink_to(root / "allowed" / "value.txt")
            (root / "allowed" / "link_outside").symlink_to(root / "outside" / "value.txt")
            try:
                result = subprocess.run(
                    [sys.executable, "-I", "-S", script, "--child", mode, folder],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    env={"PATH": os.defpath, "LC_ALL": "C.UTF-8"},
                    cwd=folder,
                    close_fds=True,
                    timeout=10,
                )
                if result.returncode not in (0, 1) or not result.stdout.strip():
                    raise RuntimeError(f"Salida {result.returncode}: {result.stderr.strip()}")
                report = json.loads(result.stdout)
                ok = report["ok"] is True and result.returncode == 0
                detail = report["detail"]
                if result.stderr.strip():
                    ok = False
                    detail += f"; stderr inesperado: {result.stderr.strip()}"
            except (subprocess.TimeoutExpired, ValueError, RuntimeError, KeyError) as error:
                ok, detail = False, f"{type(error).__name__}: {error}"

            # The parent must remain unrestricted; temporary outside data is intact.
            require((root / "outside" / "value.txt").read_text(encoding="utf-8") == "outside",
                    "El archivo temporal exterior fue modificado")
            require(os.readlink("/proc/self/ns/net") == original_net,
                    "Cambio inesperado en la red del padre")
            print(f"[{'OK' if ok else 'FAIL'}] {label}: {detail}", flush=True)
            passed += int(ok)

    print(f"Resultado: {passed}/3 comprobaciones superadas.")
    print("No cambia la configuracion del sistema ni valida aun el sandbox completo.")
    return 0 if passed == 3 else 1


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as error:
        print(f"[FAIL] {type(error).__name__}: {error}", file=sys.stderr)
        exit_code = 1
    raise SystemExit(exit_code)
