"""CLI program for human-human, human-AI, and AI-AI Gomoku games."""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import sys
import time
from pathlib import Path

from gomoku_game import BLACK, EMPTY, WHITE, GomokuGame, format_board, validate_config

_module_sequence = itertools.count(1)


def load_ai(path: Path):
    """Load a Protocol v1 AI class from a Python source path."""
    if not path.is_file():
        raise FileNotFoundError(f"AI 文件不存在：{path}")
    module_name = f"_local_gomoku_ai_{next(_module_sequence)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 AI 文件：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    ai_class = getattr(module, "GomokuAI", None)
    if ai_class is None:
        raise AttributeError(f"{path} 中没有 GomokuAI 类")
    return ai_class, str(getattr(module, "NAME", path.stem))


def choose_human_move(game: GomokuGame) -> tuple[int, int]:
    """Prompt until the user enters a currently legal coordinate."""
    stone = "黑棋 X" if game.current_player == BLACK else "白棋 O"
    while True:
        try:
            raw = input(f"{stone} 落子（输入：行 列）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出游戏。")
            raise SystemExit(0) from None
        try:
            row, col = map(int, raw.split())
            move = (row, col)
            if move in set(game.legal_moves()):
                return move
            print("该位置越界或已有棋子，请重新输入。")
        except ValueError:
            print("请输入两个整数，例如：7 7")


def choose_ai_move(ai, game: GomokuGame, time_limit: float) -> tuple[int, int]:
    """Call an AI locally and reject invalid output before changing game state."""
    start = time.perf_counter()
    move = ai.get_move(game.board_copy(), game.last_move, time_limit)
    elapsed = time.perf_counter() - start
    if move not in set(game.legal_moves()):
        raise RuntimeError(f"AI 返回非法落子：{move!r}")
    print(f"AI -> {move}（{elapsed:.3f} 秒）")
    return move


def run_game(args) -> int:
    validate_config(args.board, args.win)
    if args.time <= 0:
        raise ValueError("--time 必须为正数")
    game = GomokuGame(args.board, args.win)
    here = Path(__file__).resolve().parent
    black_ai = white_ai = None

    if args.mode == "human-ai":
        ai_class, ai_name = load_ai(Path(args.ai) if args.ai else here / "gomoku_ai.py")
        if args.human == "black":
            white_ai = ai_class(WHITE, args.board, args.win)
            print(f"你执黑棋 X；AI（{ai_name}）执白棋 O。")
        else:
            black_ai = ai_class(BLACK, args.board, args.win)
            print(f"AI（{ai_name}）执黑棋 X；你执白棋 O。")
    elif args.mode == "ai-ai":
        black_class, black_name = load_ai(
            Path(args.black_ai) if args.black_ai else here / "gomoku_ai.py"
        )
        white_class, white_name = load_ai(
            Path(args.white_ai) if args.white_ai else here / "random_ai.py"
        )
        black_ai = black_class(BLACK, args.board, args.win)
        white_ai = white_class(WHITE, args.board, args.win)
        print(f"黑棋：{black_name}；白棋：{white_name}")

    while not game.is_over:
        if not args.quiet:
            print(format_board(game.board))
        ai = black_ai if game.current_player == BLACK else white_ai
        move = choose_ai_move(ai, game, args.time) if ai else choose_human_move(game)
        game.play_move(move)

    if not args.quiet:
        print(format_board(game.board))
    if game.winner == EMPTY:
        print("和棋：棋盘已满，双方均未连成目标长度。")
    elif game.winner == BLACK:
        print("黑棋 X 获胜！")
    else:
        print("白棋 O 获胜！")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="广义五子棋：(N, K)-Gomoku")
    parser.add_argument("--mode", choices=("human-human", "human-ai", "ai-ai"),
                        default="human-ai", help="对战模式")
    parser.add_argument("--board", type=int, default=15, help="棋盘边长 N（默认 15）")
    parser.add_argument("--win", type=int, default=5, help="连珠长度 K（默认 5）")
    parser.add_argument("--time", type=float, default=5.0, help="每步 AI 时限（秒）")
    parser.add_argument("--human", choices=("black", "white"), default="black",
                        help="人机模式中玩家执棋颜色")
    parser.add_argument("--ai", help="人机模式中的 AI 文件路径")
    parser.add_argument("--black-ai", help="机机模式黑方 AI 文件路径")
    parser.add_argument("--white-ai", help="机机模式白方 AI 文件路径")
    parser.add_argument("--quiet", action="store_true", help="机机模式不逐步打印棋盘")
    parser.add_argument("--gui", action="store_true", help="启动 Tkinter 图形界面")
    args = parser.parse_args()
    if args.gui:
        from gui import main as gui_main
        gui_main()
        return 0
    try:
        return run_game(args)
    except (ValueError, OSError, ImportError, AttributeError, RuntimeError) as error:
        parser.error(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
