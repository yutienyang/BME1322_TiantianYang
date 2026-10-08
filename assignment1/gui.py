"""Tkinter GUI for the configurable Gomoku assignment.

Run directly with ``python gui.py`` or through ``python main.py --gui``.
The game rules and AI protocol are reused from the project modules; Tkinter is
only responsible for controls, drawing and click handling.
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from itertools import count
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
import importlib.util

from gomoku_game import BLACK, EMPTY, WHITE, GomokuGame, validate_config

CANVAS_SIZE = 820
MARGIN = 46
BOARD_COLOR = "#E8B86D"
_module_sequence = count(1)


class GomokuGUI:
    """A responsive GUI supporting human-human, human-AI and AI-AI games."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Gomoku (N, K)")
        self.root.geometry("1280x920")
        self.root.minsize(1100, 800)
        self._configure_fonts()

        self.mode_var = tk.StringVar(value="Human vs AI")
        self.human_var = tk.StringVar(value="Black (X)")
        self.board_var = tk.IntVar(value=15)
        self.win_var = tk.IntVar(value=5)
        self.time_var = tk.DoubleVar(value=5.0)
        self.black_ai_path_var = tk.StringVar(value="gomoku_ai.py")
        self.white_ai_path_var = tk.StringVar(value="random_ai.py")
        self.status_var = tk.StringVar(value="Choose settings, then click Start New Game.")

        self.game: GomokuGame | None = None
        self.black_ai = None
        self.white_ai = None
        self.ai_busy = False
        self.game_token = 0
        self.cell = 0.0
        self.board_left = float(MARGIN)
        self.board_top = float(MARGIN)
        self.ai_results: queue.SimpleQueue = queue.SimpleQueue()

        self._build_layout()
        self.root.after(40, self.poll_ai_results)
        self.start_game()

    def _configure_fonts(self) -> None:
        """Use comfortably readable fonts across native Tk and ttk widgets."""
        self.default_font = tkfont.Font(self.root, family="Arial", size=20)
        self.heading_font = tkfont.Font(self.root, family="Arial", size=22, weight="bold")
        self.title_font = tkfont.Font(self.root, family="Arial", size=32, weight="bold")
        self.status_font = tkfont.Font(self.root, family="Arial", size=20, weight="bold")
        self.root.option_add("*Font", self.default_font)
        style = ttk.Style(self.root)
        style.configure(".", font=self.default_font)
        style.configure("TLabel", font=self.default_font)
        style.configure("TButton", font=self.default_font, padding=(12, 10))
        style.configure("TEntry", font=self.default_font)
        style.configure("TCombobox", font=self.default_font)
        style.configure("TSpinbox", font=self.default_font)
        style.configure("Title.TLabel", font=self.title_font)
        style.configure("Heading.TLabel", font=self.heading_font)
        style.configure("Status.TLabel", font=self.status_font)

    def _build_layout(self) -> None:
        controls = ttk.Frame(self.root, padding=18)
        controls.pack(side=tk.LEFT, fill=tk.Y)
        board_frame = ttk.Frame(self.root, padding=(0, 18, 18, 18))
        board_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(controls, text="Gomoku", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(controls, text="Black X moves first. Make K or more in a row to win.",
                  wraplength=320).pack(anchor=tk.W, pady=(8, 20))

        self._labeled_combo(controls, "Mode", self.mode_var,
                            ("Human vs Human", "Human vs AI", "AI vs AI"))
        self._labeled_combo(controls, "Human color", self.human_var,
                            ("Black (X)", "White (O)"))
        self._labeled_spinbox(controls, "Board size N", self.board_var, 5, 15, 1)
        self._labeled_spinbox(controls, "Win length K", self.win_var, 3, 15, 1)
        self._labeled_spinbox(controls, "AI time limit (s)", self.time_var, 0.05, 30.0, 0.05)
        ttk.Label(controls, text="AI vs AI files", style="Heading.TLabel").pack(anchor=tk.W, pady=(14, 4))
        self._labeled_file(controls, "Black AI", self.black_ai_path_var)
        self._labeled_file(controls, "White AI", self.white_ai_path_var)

        ttk.Button(controls, text="Start New Game", command=self.start_game).pack(
            fill=tk.X, pady=(14, 5)
        )
        ttk.Button(controls, text="Quit", command=self.root.destroy).pack(fill=tk.X)
        ttk.Separator(controls).pack(fill=tk.X, pady=20)
        ttk.Label(controls, text="How to play", style="Heading.TLabel").pack(anchor=tk.W)
        ttk.Label(controls, text=(
            "- Human vs Human: take turns clicking.\n"
            "- Human vs AI: choose Black or White.\n"
            "- AI vs AI: choose two GomokuAI files.\n"
            "- Restart after changing N or K."
        ), justify=tk.LEFT, wraplength=200).pack(anchor=tk.W, pady=(5, 0))

        self.canvas = tk.Canvas(board_frame, width=CANVAS_SIZE, height=CANVAS_SIZE,
                                bg=BOARD_COLOR, highlightthickness=1,
                                highlightbackground="#7A5A28")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_board_click)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        ttk.Label(board_frame, textvariable=self.status_var, anchor=tk.CENTER,
                  style="Status.TLabel").pack(fill=tk.X, pady=(10, 0))

    @staticmethod
    def _labeled_combo(parent, label, variable, values) -> None:
        ttk.Label(parent, text=label).pack(anchor=tk.W, pady=(8, 2))
        ttk.Combobox(parent, textvariable=variable, values=values,
                     state="readonly", width=22).pack(fill=tk.X)

    @staticmethod
    def _labeled_spinbox(parent, label, variable, minimum, maximum, increment) -> None:
        ttk.Label(parent, text=label).pack(anchor=tk.W, pady=(8, 2))
        ttk.Spinbox(parent, textvariable=variable, from_=minimum, to=maximum,
                    increment=increment, width=12).pack(anchor=tk.W)

    def _labeled_file(self, parent, label, variable) -> None:
        """Add a relative/absolute AI-file input with a native file picker."""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row, text=label, width=9).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=variable, width=18).pack(side=tk.LEFT, fill=tk.X,
                                                              expand=True)
        ttk.Button(row, text="Browse", width=6,
                   command=lambda: self.choose_ai_file(variable)).pack(side=tk.RIGHT, padx=(3, 0))

    def choose_ai_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Choose Gomoku AI file", initialdir=Path(__file__).resolve().parent,
            filetypes=(("Python files", "*.py"), ("All files", "*")),
        )
        if path:
            variable.set(path)

    def start_game(self) -> None:
        """Create a new state and configure players from the visible controls."""
        try:
            board_size = int(self.board_var.get())
            win_length = int(self.win_var.get())
            time_limit = float(self.time_var.get())
            validate_config(board_size, win_length)
            if time_limit <= 0:
                raise ValueError("AI time limit must be positive")
            mode = self.mode_var.get()
            black_ai = white_ai = None
            if mode == "Human vs AI":
                ai_class, ai_name = self.load_ai_file(self.black_ai_path_var.get())
                if self.human_var.get().startswith("Black"):
                    white_ai = ai_class(WHITE, board_size, win_length)
                    opponent = f"You are Black X; {ai_name} is White O."
                else:
                    black_ai = ai_class(BLACK, board_size, win_length)
                    opponent = f"{ai_name} is Black X; you are White O."
            elif mode == "AI vs AI":
                black_class, black_name = self.load_ai_file(self.black_ai_path_var.get())
                white_class, white_name = self.load_ai_file(self.white_ai_path_var.get())
                black_ai = black_class(BLACK, board_size, win_length)
                white_ai = white_class(WHITE, board_size, win_length)
            else:
                opponent = None
        except (ValueError, OSError, ImportError, AttributeError, tk.TclError) as error:
            messagebox.showerror("Invalid settings or AI file", str(error))
            return

        self.game_token += 1  # Ignore delayed callback(s) from an old game.
        self.ai_busy = False
        self.game = GomokuGame(board_size, win_length)
        self.black_ai, self.white_ai = black_ai, white_ai
        if mode == "Human vs AI":
            self.status_var.set(f"{opponent} Click an intersection to play.")
        elif mode == "AI vs AI":
            self.status_var.set(f"AI vs AI: {black_name} (Black) vs {white_name} (White).")
        else:
            self.status_var.set("Human vs Human: Black X moves first. Click an intersection.")

        self.draw_board()
        if self._current_ai() is not None:
            self.root.after(150, self.queue_ai_turn)

    @staticmethod
    def load_ai_file(raw_path: str):
        """Load a GomokuAI class from an absolute or assignment-relative path."""
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"AI file not found: {path}")
        module_name = f"_gui_gomoku_ai_{next(_module_sequence)}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load AI file: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ai_class = getattr(module, "GomokuAI", None)
        if ai_class is None:
            raise AttributeError(f"GomokuAI class is missing from: {path}")
        return ai_class, str(getattr(module, "NAME", path.stem))

    def draw_board(self) -> None:
        """Redraw grid, coordinate labels and all stones from the game state."""
        if self.game is None:
            return
        n = self.game.board_size
        width = max(CANVAS_SIZE, self.canvas.winfo_width())
        height = max(CANVAS_SIZE, self.canvas.winfo_height())
        span = min(width, height) - 2 * MARGIN
        self.cell = span / (n - 1)
        self.board_left = (width - span) / 2
        self.board_top = (height - span) / 2
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, width, height,
                                     fill=BOARD_COLOR, outline=BOARD_COLOR)
        for index in range(n):
            x = self.board_left + index * self.cell
            y = self.board_top + index * self.cell
            self.canvas.create_line(self.board_left, y, self.board_left + span, y,
                                    fill="#44351C")
            self.canvas.create_line(x, self.board_top, x, self.board_top + span,
                                    fill="#44351C")
            coordinate_font = max(14, min(22, int(self.cell * 0.35)))
            self.canvas.create_text(x, self.board_top - 22, text=str(index), fill="#49391E",
                                    font=("Arial", coordinate_font, "bold"))
            self.canvas.create_text(self.board_left - 23, y, text=str(index), fill="#49391E",
                                    font=("Arial", coordinate_font, "bold"))

        radius = max(12, min(32, self.cell * 0.38))
        for row, values in enumerate(self.game.board):
            for col, value in enumerate(values):
                if value == EMPTY:
                    continue
                x, y = self.board_left + col * self.cell, self.board_top + row * self.cell
                if value == BLACK:
                    self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                            fill="#1D1D1D", outline="#000000", width=1)
                else:
                    self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                            fill="#F8F8F0", outline="#444444", width=1)
        if self.game.last_move is not None:
            row, col = self.game.last_move
            x, y = self.board_left + col * self.cell, self.board_top + row * self.cell
            marker = max(3, radius * 0.18)
            self.canvas.create_oval(x - marker, y - marker, x + marker, y + marker,
                                    fill="#D23A2E", outline="")

    def on_canvas_resize(self, event) -> None:
        """Keep the board large and centred when the window is resized/maximized."""
        if self.game is not None and event.width > 1 and event.height > 1:
            self.draw_board()

    def on_board_click(self, event) -> None:
        """Translate a click to its nearest board intersection for a human turn."""
        if self.game is None or self.game.is_over or self.ai_busy:
            return
        if self._current_ai() is not None:
            self.status_var.set("It is the AI's turn. Please wait.")
            return
        col = round((event.x - self.board_left) / self.cell)
        row = round((event.y - self.board_top) / self.cell)
        n = self.game.board_size
        if not (0 <= row < n and 0 <= col < n):
            return
        x, y = self.board_left + col * self.cell, self.board_top + row * self.cell
        if abs(event.x - x) > self.cell * 0.45 or abs(event.y - y) > self.cell * 0.45:
            return
        self.play_move((row, col), human=True)

    def play_move(self, move: tuple[int, int], human: bool = False) -> None:
        """Apply one move, redraw, and schedule the next AI turn when needed."""
        if self.game is None:
            return
        player = self.game.current_player
        try:
            self.game.play_move(move)
        except ValueError as error:
            if human:
                self.status_var.set(str(error))
            return
        self.draw_board()
        if self.game.is_over:
            self.finish_game()
            return
        turn = "Black X" if self.game.current_player == BLACK else "White O"
        self.status_var.set(f"{turn}'s turn.")
        if self._current_ai() is not None:
            self.root.after(120, self.queue_ai_turn)

    def _current_ai(self):
        if self.game is None:
            return None
        return self.black_ai if self.game.current_player == BLACK else self.white_ai

    def queue_ai_turn(self) -> None:
        """Run protocol AI in a background thread so Tk's event loop stays live."""
        if self.game is None or self.game.is_over or self.ai_busy:
            return
        ai = self._current_ai()
        if ai is None:
            return
        self.ai_busy = True
        token = self.game_token
        board = self.game.board_copy()
        last_move = self.game.last_move
        player = self.game.current_player
        time_limit = float(self.time_var.get())
        self.status_var.set("AI is thinking...")

        def worker() -> None:
            started = time.perf_counter()
            try:
                move, error = ai.get_move(board, last_move, time_limit), None
            except BaseException as exc:  # Show AI errors instead of crashing Tk.
                move, error = None, exc
            elapsed = time.perf_counter() - started
            self.ai_results.put((token, player, move, error, elapsed))

        threading.Thread(target=worker, daemon=True).start()

    def poll_ai_results(self) -> None:
        """Apply worker results from Tk's main thread (Tk itself is not thread-safe)."""
        while True:
            try:
                result = self.ai_results.get_nowait()
            except queue.Empty:
                break
            self.finish_ai_turn(*result)
        self.root.after(40, self.poll_ai_results)

    def finish_ai_turn(self, token, player, move, error, elapsed) -> None:
        """Validate a background result on the Tk thread before applying it."""
        if token != self.game_token or self.game is None:
            return
        self.ai_busy = False
        if error is not None:
            self.status_var.set(f"AI exception: {error!r}")
            messagebox.showerror("AI exception", repr(error))
            return
        legal = set(self.game.legal_moves())
        if player != self.game.current_player or move not in legal:
            self.status_var.set(f"AI returned an illegal move: {move!r}")
            messagebox.showerror("Illegal AI move", repr(move))
            return
        self.status_var.set(f"AI played {move} in {elapsed:.3f} seconds.")
        self.play_move(move)

    def finish_game(self) -> None:
        if self.game is None:
            return
        if self.game.winner == EMPTY:
            message = "Draw: the board is full without a winning line."
        elif self.game.winner == BLACK:
            message = "Black X wins!"
        else:
            message = "White O wins!"
        self.status_var.set(message)
        messagebox.showinfo("Game over", message)


def main() -> None:
    root = tk.Tk()
    GomokuGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
