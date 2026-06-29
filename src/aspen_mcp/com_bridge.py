"""COM 桥接 — 向后兼容壳。

实际实现在 bridge/ 子包中。此模块保留 aspen 全局单例，
确保所有现有 tools/*.py 的 import 不受影响。
"""

from __future__ import annotations

from .bridge import make_bridge

aspen = make_bridge()
