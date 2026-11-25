#!/usr/bin/env python3
"""动作队列：把"分块策略返回的整块动作"变成"每步一个动作"（纯函数，零依赖）。

为什么单独成模块：
  官方两个基线对动作的返回形态不同——
    ACT 返回单步 (action_dim,)
    DP  返回整块 (n_action_steps, action_dim)，官方是**开环执行整块**再重新推理
  harness 每步只问一个动作，所以分块策略必须排队。这段逻辑与"哪个策略"无关，
  抽出来才能复用：接第三个官方策略时不用再写一遍。

设计约束（都是踩过的坑）：
  1. **队列空才推理**——每步都推理等于把整块白算 n-1 次，且行为偏离官方；
  2. **reset 必须清空**——否则跨集会串动作；
  3. 维度不整除要报错，不能猜。
"""
from __future__ import annotations

from collections import deque
from typing import Any, Iterable

import numpy as np


class ActionQueue:
    """无状态的输入、有状态的输出：喂整块，吐单步。"""

    def __init__(self, action_dim: int = 14) -> None:
        if action_dim <= 0:
            raise ValueError(f"action_dim 必须为正（实际 {action_dim}）")
        self.action_dim = int(action_dim)
        self._q: deque[np.ndarray] = deque()

    # ---------------------------------------------------------------- 状态
    @property
    def pending(self) -> int:
        return len(self._q)

    def clear(self) -> None:
        self._q.clear()

    # ---------------------------------------------------------------- 入队
    def _rows(self, chunk: Any) -> list[np.ndarray]:
        a = np.asarray(chunk, dtype=np.float32)
        if a.size == 0:
            raise ValueError("策略返回空动作")
        if a.size % self.action_dim != 0:
            raise ValueError(
                f"动作维度 {a.size} 不是 action_dim={self.action_dim} 的整数倍（块长度不整）")
        return [row.reshape(self.action_dim) for row in a.reshape(-1, self.action_dim)]

    def push(self, chunk: Any) -> int:
        """把一块动作放入队列，返回放入的步数。"""
        rows = self._rows(chunk)
        self._q.extend(rows)
        return len(rows)

    # ---------------------------------------------------------------- 出队
    def pop(self) -> np.ndarray:
        if not self._q:
            raise IndexError("队列为空：应先 push（且只在队列空时推理）")
        return self._q.popleft()

    def pop_or_fill(self, chunk: Any) -> np.ndarray:
        """一步拿到动作：队列空则先用 chunk 填充，再吐一步。

        这正是"队列空才推理"的落点——调用方只在返回空时才去推理。
        """
        if not self._q:
            self.push(chunk)
        return self.pop()

    def drain(self) -> Iterable[np.ndarray]:
        while self._q:
            yield self._q.popleft()
