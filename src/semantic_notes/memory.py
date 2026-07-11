import resource
from pathlib import Path


CGROUP_MEMORY_CURRENT = Path("/sys/fs/cgroup/memory.current")
CGROUP_MEMORY_MAX = Path("/sys/fs/cgroup/memory.max")
MIB = 1024**2


def current_rss_mb() -> float | None:
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def max_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def get_container_memory_usage() -> tuple[int | None, int | None, float | None]:
    try:
        current_bytes = int(CGROUP_MEMORY_CURRENT.read_text().strip())
        max_content = CGROUP_MEMORY_MAX.read_text().strip()
    except (OSError, ValueError):
        return None, None, None

    if max_content == "max":
        return current_bytes, None, None

    try:
        max_bytes = int(max_content)
    except ValueError:
        return current_bytes, None, None

    if max_bytes <= 0:
        return current_bytes, max_bytes, None

    return current_bytes, max_bytes, (current_bytes / max_bytes) * 100


def format_container_memory() -> str:
    current_bytes, max_bytes, percent = get_container_memory_usage()
    if current_bytes is None:
        current_rss = current_rss_mb()
        if current_rss is None:
            return f"memory=unavailable max_rss={max_rss_mb():.1f}MiB"
        return f"rss={current_rss:.1f}MiB max_rss={max_rss_mb():.1f}MiB"

    current_mib = current_bytes / MIB
    if max_bytes is None:
        return f"container_memory={current_mib:.1f}MiB/no_limit"

    max_mib = max_bytes / MIB
    if percent is None:
        return f"container_memory={current_mib:.1f}MiB/{max_mib:.1f}MiB"
    return f"container_memory={current_mib:.1f}MiB/{max_mib:.1f}MiB {percent:.1f}%"
