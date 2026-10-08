"""Reproducible local experiments for Assignment 1 (standard library only)."""

from __future__ import annotations

import argparse
import importlib.util
import statistics
import time
from pathlib import Path

DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


def load_ai(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GomokuAI


def is_win(board, row, col, player, win_length):
    n = len(board)
    for dr, dc in DIRECTIONS:
        count = 1
        for sign in (-1, 1):
            r, c = row + sign * dr, col + sign * dc
            while 0 <= r < n and 0 <= c < n and board[r][c] == player:
                count += 1
                r += sign * dr
                c += sign * dc
        if count >= win_length:
            return True
    return False


def run_match(own_class, other_class, board_size, win_length, games, time_limit):
    """Return win/draw counts, mean game length, mean and max own-AI time."""
    own_wins = draws = 0
    lengths, own_times = [], []
    for game_no in range(games):
        own_is_black = game_no % 2 == 0
        black = (own_class if own_is_black else other_class)(1, board_size, win_length)
        white = (other_class if own_is_black else own_class)(2, board_size, win_length)
        board = [[0] * board_size for _ in range(board_size)]
        player, last_move = 1, None
        for ply in range(1, board_size * board_size + 1):
            ai = black if player == 1 else white
            started = time.perf_counter()
            move = ai.get_move([row[:] for row in board], last_move, time_limit)
            elapsed = time.perf_counter() - started
            if isinstance(ai, own_class):
                own_times.append(elapsed)
            if (not isinstance(move, tuple) or len(move) != 2
                    or not all(isinstance(value, int) for value in move)):
                raise RuntimeError(f"AI returned invalid move type: {move!r}")
            row, col = move
            if not (0 <= row < board_size and 0 <= col < board_size) or board[row][col] != 0:
                raise RuntimeError(f"AI returned illegal move: {move!r}")
            board[row][col] = player
            last_move = move
            if is_win(board, row, col, player, win_length):
                lengths.append(ply)
                own_wins += player == (1 if own_is_black else 2)
                break
            player = 3 - player
        else:
            lengths.append(board_size * board_size)
            draws += 1
    return own_wins, draws, statistics.mean(lengths), statistics.mean(own_times), max(own_times)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gomoku AI local benchmark")
    parser.add_argument("--board", type=int, default=9)
    parser.add_argument("--win", type=int, default=4)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--time", type=float, default=0.05)
    parser.add_argument("--self-play", action="store_true")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    own_class = load_ai("benchmark_own", here / "gomoku_ai.py")
    other_class = own_class if args.self_play else load_ai("benchmark_random", here / "random_ai.py")
    wins, draws, length, mean_time, max_time = run_match(
        own_class, other_class, args.board, args.win, args.games, args.time
    )
    opponent = "self" if args.self_play else "random_ai"
    print(f"AI vs {opponent} | N={args.board}, K={args.win}, games={args.games}")
    print(f"own wins={wins}, losses={args.games - wins - draws}, draws={draws}")
    print(f"average game length={length:.2f} plies")
    print(f"own mean thinking time={mean_time:.4f}s, max={max_time:.4f}s")


if __name__ == "__main__":
    main()
