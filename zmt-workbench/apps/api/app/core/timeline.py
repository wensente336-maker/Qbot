"""时间轴重映射（核心算法，TD 4.3）。

给定删除区间集合 S = [(start, end), ...]（毫秒），对原时间轴上的点 t，
新时间 t' = t − Σ{ start <= t 的删除区间时长 }。

删除区间按 start 升序合并后，构建「按 start 升序的前缀和查找表 + 二分」：
任意位于 cut start 处或之后的点统一减去已累计的删除时长，实现为 O(log n) 查询。
"""

from bisect import bisect_right


def merge_cuts(cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """排序并合并重叠/相邻删除区间，返回互不重叠的有序区间列表。"""
    if not cuts:
        return []
    normalized = sorted((min(s, e), max(s, e)) for s, e in cuts if e > s)
    merged: list[tuple[int, int]] = [normalized[0]]
    for s, e in normalized[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def build_remap(cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """构建查找表 [(cut_start, cumulative_removed), ...]，按 cut_start 升序。"""
    table: list[tuple[int, int]] = []
    acc = 0
    for s, e in merge_cuts(cuts):
        acc += e - s
        table.append((s, acc))
    return table


def remap(t: int, table: list[tuple[int, int]]) -> int:
    """二分定位 start <= t 的全部删除区间，返回新时间轴时间。"""
    starts = [r[0] for r in table]
    i = bisect_right(starts, t)
    offset = table[i - 1][1] if i > 0 else 0
    return t - offset


def translate_interval(
    start: int, end: int, table: list[tuple[int, int]]
) -> tuple[int, int]:
    """将原时间轴上的区间 [start, end] 映射到新时间轴。"""
    return remap(start, table), remap(end, table)
