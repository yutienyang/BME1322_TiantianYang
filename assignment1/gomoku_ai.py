"""Time-bounded Alpha-Beta Gomoku AI for the course Protocol v1.

All board and winning-line parameters come from the constructor, so the AI
adapts to the referee's (N, K) configuration without external dependencies.
"""

from __future__ import annotations

import math
import time

NAME = "Adaptive AlphaBeta"

EMPTY, BLACK, WHITE = 0, 1, 2
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


class SearchTimeout(Exception):
    """Internal signal; it is caught by get_move before returning to the arena."""


class GomokuAI:
    """MiniMax player with Alpha-Beta pruning and iterative deepening."""

    def __init__(self, player_id: int, board_size: int, win_length: int):
        if player_id not in (BLACK, WHITE):
            raise ValueError("player_id must be 1 or 2")
        if board_size < 3 or not 3 <= win_length <= board_size:
            raise ValueError("invalid board_size/win_length")
        self.player_id = player_id
        self.opponent_id = WHITE if player_id == BLACK else BLACK
        self.board_size = board_size
        self.win_length = win_length
        self.deadline = 0.0
        self.win_score = 10 ** (self.win_length + 3)

    def get_move(self, board, last_opponent_move, time_limit):
        """Return a legal coordinate tuple without mutating the input board."""
        work_board = [row[:] for row in board]
        legal = self._all_empty(work_board)
        # The referee never calls an AI on a full board; retain a total fallback.
        if not legal:
            return (0, 0)

        # Keep scheduler/return margin rather than consuming the entire limit.
        allowed = max(0.001, float(time_limit) * 0.88)
        self.deadline = time.perf_counter() + allowed
        raw_candidates = self._order_moves(
            work_board, self._candidate_moves(work_board), limit=False
        )
        candidates = self._order_moves(work_board, raw_candidates)
        best_move = candidates[0] if candidates else legal[0]

        try:
            # Tactical checks use the full local candidate set, not the search cap.
            own_wins = self._winning_moves(work_board, self.player_id, raw_candidates)
            if own_wins:
                return own_wins[0]
            opponent_wins = self._winning_moves(
                work_board, self.opponent_id, raw_candidates
            )
            if opponent_wins:
                return opponent_wins[0]

            # A fork creates two separate winning points.  If there is no direct
            # win to answer, it is a forced win; conversely, a unique enemy fork
            # must be occupied now rather than evaluated only at the horizon.
            own_forks = self._fork_moves(work_board, self.player_id, raw_candidates)
            if own_forks:
                return own_forks[0]
            opponent_forks = self._fork_moves(
                work_board, self.opponent_id, raw_candidates
            )
            fork_block = self._block_opponent_forks(work_board, opponent_forks)
            if fork_block is not None:
                return fork_block

            max_depth = 6 if self.board_size <= 6 else (5 if self.board_size <= 9 else 4)
            for depth in range(1, max_depth + 1):
                _, move = self._root_search(work_board, depth, best_move)
                if move is not None:  # Keep only results from completed iterations.
                    best_move = move
        except SearchTimeout:
            pass
        return best_move

    def _root_search(self, board, depth, previous_best):
        alpha, beta = -math.inf, math.inf
        best_score, best_move = -math.inf, None
        moves = self._order_moves(board, self._candidate_moves(board), previous_best)
        for row, col in moves:
            self._check_time()
            board[row][col] = self.player_id
            score = self._alphabeta(board, depth - 1, alpha, beta,
                                    self.opponent_id, (row, col))
            board[row][col] = EMPTY
            if score > best_score:
                best_score, best_move = score, (row, col)
            alpha = max(alpha, best_score)
        return best_score, best_move

    def _alphabeta(self, board, depth, alpha, beta, player_to_move, last_move):
        self._check_time()
        previous_player = WHITE if player_to_move == BLACK else BLACK
        if self._is_win(board, last_move, previous_player):
            return (self.win_score + depth if previous_player == self.player_id
                    else -self.win_score - depth)
        if depth == 0:
            return self._evaluate(board)

        moves = self._order_moves(board, self._candidate_moves(board))
        if not moves:
            return 0
        if player_to_move == self.player_id:
            value = -math.inf
            for row, col in moves:
                board[row][col] = player_to_move
                value = max(value, self._alphabeta(
                    board, depth - 1, alpha, beta, self.opponent_id, (row, col)
                ))
                board[row][col] = EMPTY
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            return value

        value = math.inf
        for row, col in moves:
            board[row][col] = player_to_move
            value = min(value, self._alphabeta(
                board, depth - 1, alpha, beta, self.player_id, (row, col)
            ))
            board[row][col] = EMPTY
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value

    def _candidate_moves(self, board):
        """Search empty neighbours of stones instead of the entire board."""
        occupied = [(r, c) for r in range(self.board_size)
                    for c in range(self.board_size) if board[r][c] != EMPTY]
        if not occupied:
            middle = self.board_size // 2
            return [(middle, middle)]
        candidates = set()
        for row, col in occupied:
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    r, c = row + dr, col + dc
                    if (0 <= r < self.board_size and 0 <= c < self.board_size
                            and board[r][c] == EMPTY):
                        candidates.add((r, c))
        return list(candidates) or self._all_empty(board)

    def _order_moves(self, board, moves, first=None, limit=True):
        """Prefer threatening, blocking and central moves for stronger pruning."""
        center = (self.board_size - 1) / 2

        def key(move):
            row, col = move
            own = self._line_potential(board, row, col, self.player_id)
            opponent = self._line_potential(board, row, col, self.opponent_id)
            centrality = -abs(row - center) - abs(col - center)
            return own * 12 + opponent * 13 + centrality

        ordered = sorted(moves, key=key, reverse=True)
        if first in ordered:
            ordered.remove(first)
            ordered.insert(0, first)
        if not limit:
            return ordered
        cap = 18 if self.board_size <= 6 else (15 if self.board_size <= 9 else 12)
        return ordered[:cap]

    def _line_potential(self, board, row, col, player):
        """Longest same-colour line formed if player occupies this empty cell."""
        best = 1
        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (-1, 1):
                r, c = row + sign * dr, col + sign * dc
                while (0 <= r < self.board_size and 0 <= c < self.board_size
                       and board[r][c] == player):
                    count += 1
                    r += sign * dr
                    c += sign * dc
            best = max(best, count)
        return best

    def _would_win(self, board, move, player):
        row, col = move
        board[row][col] = player
        result = self._is_win(board, move, player)
        board[row][col] = EMPTY
        return result

    def _winning_moves(self, board, player, moves=None):
        """Return all local moves that let ``player`` win on this very turn."""
        if moves is None:
            moves = self._candidate_moves(board)
        wins = []
        for index, move in enumerate(moves):
            if index % 8 == 0:
                self._check_time()
            if self._would_win(board, move, player):
                wins.append(move)
        return wins

    def _fork_moves(self, board, player, moves):
        """Find moves that leave at least two distinct immediate wins next turn."""
        forks = []
        for index, move in enumerate(moves):
            if index % 4 == 0:
                self._check_time()
            row, col = move
            board[row][col] = player
            if not self._is_win(board, move, player):
                next_wins = self._winning_moves(board, player)
                if len(next_wins) >= 2:
                    forks.append(move)
            board[row][col] = EMPTY
        return forks

    def _block_opponent_forks(self, board, opponent_forks):
        """Return a fork square whose occupation removes every enemy fork.

        A line with two open ends can give the opponent two *candidate* fork
        moves, yet occupying either end may neutralise both.  Therefore the
        number of forks alone is not enough to decide that a position is lost.
        """
        for index, move in enumerate(opponent_forks):
            if index % 4 == 0:
                self._check_time()
            row, col = move
            board[row][col] = self.player_id
            remaining = self._fork_moves(
                board, self.opponent_id, self._candidate_moves(board)
            )
            board[row][col] = EMPTY
            if not remaining:
                return move
        return None

    def _is_win(self, board, move, player):
        row, col = move
        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (-1, 1):
                r, c = row + sign * dr, col + sign * dc
                while (0 <= r < self.board_size and 0 <= c < self.board_size
                       and board[r][c] == player):
                    count += 1
                    r += sign * dr
                    c += sign * dc
            if count >= self.win_length:
                return True
        return False

    def _evaluate(self, board):
        """Score K-windows and open/closed runs from this AI's perspective."""
        score, base = 0, 10
        for row in range(self.board_size):
            for col in range(self.board_size):
                for dr, dc in DIRECTIONS:
                    end_row = row + (self.win_length - 1) * dr
                    end_col = col + (self.win_length - 1) * dc
                    if not (0 <= end_row < self.board_size
                            and 0 <= end_col < self.board_size):
                        continue
                    own = opponent = 0
                    for step in range(self.win_length):
                        value = board[row + step * dr][col + step * dc]
                        if value == self.player_id:
                            own += 1
                        elif value == self.opponent_id:
                            opponent += 1
                    if own and not opponent:
                        score += base ** own
                    elif opponent and not own:
                        score -= int(1.15 * (base ** opponent))
        # Window counts alone do not distinguish an open four from a blocked
        # four.  Add maximal-line features so open K-2/K-1 threats dominate.
        score += self._run_score(board, self.player_id)
        score -= int(1.25 * self._run_score(board, self.opponent_id))
        return score

    def _run_score(self, board, player):
        """Score each maximal run once, with a large bonus for open threats."""
        total = 0
        n, k = self.board_size, self.win_length
        for row in range(n):
            for col in range(n):
                if board[row][col] != player:
                    continue
                for dr, dc in DIRECTIONS:
                    previous_row, previous_col = row - dr, col - dc
                    if (0 <= previous_row < n and 0 <= previous_col < n
                            and board[previous_row][previous_col] == player):
                        continue  # This run was/will be counted from its first stone.
                    length = 0
                    r, c = row, col
                    while 0 <= r < n and 0 <= c < n and board[r][c] == player:
                        length += 1
                        r += dr
                        c += dc
                    open_ends = int(0 <= previous_row < n and 0 <= previous_col < n
                                    and board[previous_row][previous_col] == EMPTY)
                    open_ends += int(0 <= r < n and 0 <= c < n and board[r][c] == EMPTY)
                    total += self._run_value(length, open_ends, k)
        return total

    @staticmethod
    def _run_value(length, open_ends, win_length):
        """Return a K-adaptive run value; blocked runs have no extension value."""
        if length >= win_length:
            return 10 ** (win_length + 2)
        if open_ends == 0:
            return 0
        remaining = win_length - length
        if remaining == 1:
            return 10 ** (win_length + (1 if open_ends == 2 else 0))
        if remaining == 2:
            return 10 ** (win_length if open_ends == 2 else win_length - 1)
        return 10 ** min(win_length - 2, max(1, length + open_ends - 1))

    def _all_empty(self, board):
        return [(r, c) for r in range(self.board_size)
                for c in range(self.board_size) if board[r][c] == EMPTY]

    def _check_time(self):
        if time.perf_counter() >= self.deadline:
            raise SearchTimeout
