"""Rules and state management for configurable (N, K)-Gomoku."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional

EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


def validate_config(board_size: int, win_length: int) -> None:
    """Validate a general Gomoku configuration."""
    if board_size < 3:
        raise ValueError("Board size N must be at least 3")
    if not 3 <= win_length <= board_size:
        raise ValueError("Win length must satisfy 3 <= K <= N")


def is_winning_move(board: list[list[int]], row: int, col: int, player: int,
                    win_length: int) -> bool:
    """Check only the four lines crossing a newly placed stone."""
    n = len(board)
    for dr, dc in DIRECTIONS:
        count = 1
        for sign in (1, -1):
            r, c = row + sign * dr, col + sign * dc
            while 0 <= r < n and 0 <= c < n and board[r][c] == player:
                count += 1
                r += sign * dr
                c += sign * dc
        if count >= win_length:  # Long lines are wins in this assignment.
            return True
    return False


@dataclass
class GomokuGame:
    """UI-independent game state shared by all three game modes."""

    board_size: int = 15
    win_length: int = 5
    board: list[list[int]] = field(init=False)
    current_player: int = field(default=BLACK, init=False)
    winner: int = field(default=EMPTY, init=False)
    last_move: Optional[tuple[int, int]] = field(default=None, init=False)
    moves_played: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        validate_config(self.board_size, self.win_length)
        self.board = [[EMPTY] * self.board_size for _ in range(self.board_size)]

    @property
    def is_draw(self) -> bool:
        return self.winner == EMPTY and self.moves_played == self.board_size ** 2

    @property
    def is_over(self) -> bool:
        return self.winner != EMPTY or self.is_draw

    def legal_moves(self) -> Iterator[tuple[int, int]]:
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.board[row][col] == EMPTY:
                    yield (row, col)

    def play_move(self, move: tuple[int, int]) -> None:
        """Apply one legal move and update terminal state/turn."""
        if self.is_over:
            raise ValueError("The game is already over")
        if (not isinstance(move, tuple) or len(move) != 2
                or any(isinstance(value, bool) or not isinstance(value, int)
                       for value in move)):
            raise ValueError("A move must be an (int, int) tuple")
        row, col = move
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            raise ValueError(f"Move {move} is outside the board")
        if self.board[row][col] != EMPTY:
            raise ValueError(f"Cell {move} is already occupied")

        player = self.current_player
        self.board[row][col] = player
        self.last_move = move
        self.moves_played += 1
        if is_winning_move(self.board, row, col, player, self.win_length):
            self.winner = player
        elif not self.is_draw:
            self.current_player = WHITE if player == BLACK else BLACK

    def board_copy(self) -> list[list[int]]:
        return [row[:] for row in self.board]


def format_board(board: list[list[int]]) -> str:
    """Return a coordinate-labelled plain-text board suitable for a CLI."""
    n = len(board)
    width = len(str(n - 1))
    stones = {EMPTY: ".", BLACK: "X", WHITE: "O"}
    header = " " * (width + 1) + " " + " ".join(
        f"{col:>{width}}" for col in range(n)
    )
    lines = [header]
    for row, values in enumerate(board):
        cells = " ".join(f"{stones[value]:>{width}}" for value in values)
        lines.append(f"{row:>{width}} {cells}")
    return "\n".join(lines)
