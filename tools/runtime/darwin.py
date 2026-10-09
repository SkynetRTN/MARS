"""Finite macOS address-space growth allowance above bootstrap mappings.

macOS includes large system/loader mappings in virtual size before any tool
imports. A Linux-style absolute 4-GiB RLIMIT_AS can therefore be below current
usage and is rejected by XNU. Measure once, before loading the call, then bound
additional address space; never retry with an unlimited ceiling.

ABI: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/proc_info.h
Limit: https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_resource.c
"""

import ctypes
import errno
import os
import sys


class TaskInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("virtual_size", "resident_size", "total_user", "total_system",
                 "threads_user", "threads_system")] + [(name, ctypes.c_int32) for name in
                ("policy", "faults", "pageins", "cow_faults", "messages_sent",
                 "messages_received", "syscalls_mach", "syscalls_unix", "switches",
                 "thread_count", "running_count", "priority")]


def bootstrap_size() -> int:
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                    ctypes.c_void_p, ctypes.c_int]
    library.proc_pidinfo.restype = ctypes.c_int
    info = TaskInfo()
    size = ctypes.sizeof(info)
    # PROC_PIDTASKINFO = 4; a short/failed read is not permission to drop limits.
    received = library.proc_pidinfo(os.getpid(), 4, 0, ctypes.byref(info), size)
    if received != size or info.virtual_size == 0:
        raise OSError(ctypes.get_errno() or errno.EIO, "Cannot measure macOS bootstrap address space.")
    return info.virtual_size


def memory_ceiling(allowance: int) -> int:
    baseline = bootstrap_size()
    ceiling = baseline + allowance
    sys.stderr.write(f"MARS macOS memory: bootstrap={baseline}, allowance={allowance}, ceiling={ceiling} bytes\n")
    return ceiling
