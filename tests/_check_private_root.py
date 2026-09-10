"""Disposable prerequisite probe for a private filesystem root, not a sandbox.

Run as a normal user with Python 3.10. Uses only the standard library.
Two children test fixed operations on files created by this script. No LLM,
MCP, Docker, exec/eval, installation or system configuration changes.

The child creates user/mount/network namespaces, mounts a temporary root,
exposes either two temporary directories or none, calls chroot and drops
its effective/permitted/inheritable capabilities. The parent stays outside.

Not covered: arbitrary allowed_directories, pre-existing hard links, moving
mount sources, Python import/builtin restrictions, time/RAM limits, signals,
supplementary groups, inherited-resource/IPC attacks, or the real worker.
Do not copy this probe into production as a finished isolation mechanism.

References:
https://man7.org/linux/man-pages/man7/user_namespaces.7.html
https://man7.org/linux/man-pages/man2/mount.2.html
https://man7.org/linux/man-pages/man2/chroot.2.html
https://man7.org/linux/man-pages/man2/capset.2.html
"""

import ctypes
import errno
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


CLONE_NEWUSER = 0x10000000
CLONE_NEWNS = 0x00020000
CLONE_NEWNET = 0x40000000
MS_RDONLY, MS_NOSUID, MS_NODEV, MS_NOEXEC = 1, 2, 4, 8
MS_REMOUNT, MS_BIND, MS_REC, MS_PRIVATE = 32, 4096, 16384, 1 << 18
PR_SET_NO_NEW_PRIVS = 38
CAP_VERSION_3 = 0x20080522


class CapHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]


class CapData(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def checked(result, operation):
    if result < 0:
        number = ctypes.get_errno()
        raise OSError(number, f"{operation}: {os.strerror(number)}")


def blocked(operation, expected_errors, label):
    try:
        operation()
    except OSError as error:
        require(error.errno in expected_errors, f"{label}: error inesperado {error}")
    else:
        raise RuntimeError(f"No se bloqueo: {label}")


def load_libc():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                           ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    libc.prctl.restype = ctypes.c_int
    for name in ("capset", "capget"):
        function = getattr(libc, name)
        function.argtypes = [ctypes.POINTER(CapHeader), ctypes.POINTER(CapData)]
        function.restype = ctypes.c_int
    return libc


def check_child(folder, expose):
    libc = load_libc()
    uid, gid = os.getuid(), os.getgid()
    root = folder / "root"
    outside = folder / "outside.txt"
    old_mount = os.readlink("/proc/self/ns/mnt")
    old_network = os.readlink("/proc/self/ns/net")
    require(outside.read_bytes() == b"outside", "Preparacion del archivo exterior")
    outside.write_bytes(b"outside")

    checked(libc.unshare(CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWNET),
            "crear namespaces de usuario, montajes y red")
    # Map only our own host identity. Inside we are UID/GID 1000, not root.
    Path("/proc/self/setgroups").write_text("deny\n", encoding="ascii")
    Path("/proc/self/uid_map").write_text(f"1000 {uid} 1\n", encoding="ascii")
    Path("/proc/self/gid_map").write_text(f"1000 {gid} 1\n", encoding="ascii")
    require(os.getuid() == 1000 and os.getgid() == 1000, "Mapeo de identidad")
    require(os.readlink("/proc/self/ns/mnt") != old_mount, "Namespace de montajes")
    require(os.readlink("/proc/self/ns/net") != old_network, "Namespace de red")

    checked(libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None),
            "hacer privados los montajes del hijo")
    flags = MS_NOSUID | MS_NODEV | MS_NOEXEC
    checked(libc.mount(b"tmpfs", os.fsencode(root), b"tmpfs", flags,
                       ctypes.c_char_p(b"size=2m,mode=755")), "montar raiz temporal")
    if expose:
        for name in ("area1", "area2"):
            destination = root / name
            destination.mkdir()
            checked(libc.mount(os.fsencode(folder / name), os.fsencode(destination),
                               None, MS_BIND, None), f"exponer {name}")
    # Only the root mount becomes read-only; the two child bind mounts stay writable.
    checked(libc.mount(None, os.fsencode(root), None,
                       MS_REMOUNT | MS_RDONLY | flags, None), "raiz de solo lectura")

    os.chroot(root)
    os.chdir("/")
    checked(libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0), "no_new_privs")
    header = CapHeader(CAP_VERSION_3, 0)
    capabilities = (CapData * 2)()
    checked(libc.capset(ctypes.byref(header), capabilities), "retirar capabilities")
    checked(libc.capget(ctypes.byref(header), capabilities), "comprobar capabilities")
    require(all(item.effective == item.permitted == item.inheritable == 0
                for item in capabilities), "Quedan capabilities activas o permitidas")
    blocked(lambda: os.chroot("/"), {errno.EPERM}, "repetir chroot sin privilegios")

    for name in ("area1", "area2"):
        value = Path("/") / name / "value.txt"
        if expose:
            require(value.read_bytes() == b"inside", "Lectura permitida")
            value.write_bytes(b"updated")
            require(value.read_bytes() == b"updated", "Escritura permitida")
            blocked(lambda: (value.parent / "escape").read_bytes(),
                    {errno.ENOENT}, "enlace hacia archivo exterior")
        else:
            blocked(lambda: value.read_bytes(), {errno.ENOENT}, "lectura con lista vacia")
            blocked(lambda: value.write_bytes(b"bad"), {errno.ENOENT},
                    "escritura con lista vacia")

    blocked(lambda: outside.read_bytes(), {errno.ENOENT}, "leer archivo exterior")
    blocked(lambda: outside.write_bytes(b"bad"), {errno.ENOENT}, "escribir fuera")
    blocked(lambda: os.truncate(outside, 0), {errno.ENOENT}, "truncar fuera")
    blocked(lambda: outside.stat(), {errno.ENOENT}, "stat exterior")
    blocked(lambda: Path("/new.txt").write_bytes(b"bad"), {errno.EROFS}, "crear en raiz")
    print("raiz privada; accesos comprobados; capabilities E/P/I a cero", flush=True)


def run_probe(expose):
    mount_before = os.readlink("/proc/self/ns/mnt")
    network_before = os.readlink("/proc/self/ns/net")
    with tempfile.TemporaryDirectory(prefix="agentsmith-root-probe-") as temporary:
        folder = Path(temporary)
        (folder / "root").mkdir()
        (folder / "outside.txt").write_bytes(b"outside")
        for name in ("area1", "area2"):
            (folder / name).mkdir()
            (folder / name / "value.txt").write_bytes(b"inside")
            (folder / name / "escape").symlink_to(folder / "outside.txt")
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-u", str(Path(__file__).resolve()),
             "--child", str(folder), "allow" if expose else "empty"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=10, close_fds=True, env={},
        )
        require(result.returncode == 0,
                (result.stdout + result.stderr).strip() or f"Salida {result.returncode}")
        require(os.readlink("/proc/self/ns/mnt") == mount_before, "Montajes del padre")
        require(os.readlink("/proc/self/ns/net") == network_before, "Red del padre")
        require((folder / "outside.txt").read_bytes() == b"outside", "Archivo exterior")
        require(list((folder / "root").iterdir()) == [], "La raiz temporal no desaparecio")
        expected = b"updated" if expose else b"inside"
        for name in ("area1", "area2"):
            require((folder / name / "value.txt").read_bytes() == expected,
                    "Cambios en los directorios temporales")
        return result.stdout.strip()


def main():
    require(sys.platform == "linux", "Esta prueba requiere Linux")
    require(os.geteuid() != 0, "Ejecuta como usuario normal, sin sudo")
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        require(sys.argv[3] in ("allow", "empty"), "Modo de hijo desconocido")
        check_child(Path(sys.argv[2]), sys.argv[3] == "allow")
        return 0
    require(len(sys.argv) == 1, "No se necesitan argumentos")
    print(f"Python: {platform.python_version()}")
    print(f"Sistema: Linux {platform.release()} {platform.machine()}")
    print("Prerrequisitos de raiz privada: NO es un sandbox completo.", flush=True)
    passed = 0
    for expose, label in ((True, "RAIZ_DOS_DIRECTORIOS"), (False, "RAIZ_LISTA_VACIA")):
        try:
            detail = run_probe(expose)
        except Exception as error:
            print(f"[FAIL] {label}: {type(error).__name__}: {error}", flush=True)
        else:
            passed += 1
            print(f"[OK] {label}: {detail}", flush=True)
    print(f"Resultado: {passed}/2 comprobaciones superadas.")
    return 0 if passed == 2 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[FAIL] {type(error).__name__}: {error}", flush=True)
        raise SystemExit(1)
