import ctypes
import os
from pathlib import Path


CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
CLONE_NEWNET = 0x40000000


def checked(result, operation):
    if result < 0:
        number = ctypes.get_errno()
        raise OSError(
            number,
            f"{operation}: {os.strerror(number)}",
        )


def load_libc():
    libc = ctypes.CDLL(None, use_errno=True)

    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int

    return libc


def create_namespaces(libc):
    host_uid = os.getuid()
    host_gid = os.getgid()

    flags = CLONE_NEWUSER | CLONE_NEWNS | CLONE_NEWNET
    checked(libc.unshare(flags), "unshare")

    Path("/proc/self/setgroups").write_text(
        "deny\n",
        encoding="ascii",
    )

    Path("/proc/self/uid_map").write_text(
        f"1000 {host_uid} 1\n",
        encoding="ascii",
    )

    Path("/proc/self/gid_map").write_text(
        f"1000 {host_gid} 1\n",
        encoding="ascii",
    )

    if os.getuid() != 1000 or os.getgid() != 1000:
        raise RuntimeError("No se pudo configurar el usuario del sandbox")