# 广义五子棋与对抗搜索

## 运行游戏

在本目录运行：

```bash
# 图形界面（推荐演示使用）
python main.py --gui

# 人人对战
python main.py --mode human-human --board 9 --win 4

# 人机对战；玩家执黑棋
python main.py --mode human-ai --board 15 --win 5 --human black --time 5

# 机机对战；默认是本 AI 对随机 AI
python main.py --mode ai-ai --board 9 --win 4 --time 1
```

CLI 坐标格式为 `行 列`，从左上角的 `0 0` 开始。黑棋是 `X`，白棋是 `O`。

图形界面使用 Python 标准库 Tkinter，窗口内可选择人人、人机、机机模式，并设置棋盘边长 N、连珠长度 K、玩家执棋颜色和 AI 时限；AI 计算在后台线程运行，不会卡住窗口。

要在 GUI 中观看与同学 AI 的对战：选择 **AI vs AI**，将 **Black AI** 保持为 `gomoku_ai.py`，把 **White AI** 设置为例如 `other_player/gomoku_ai.py`，然后点击 **Start New Game**。路径既可以相对于 `assignment1/`，也可以是绝对路径；两个文件都必须实现课程规定的 `GomokuAI` 接口。

## 用课程裁判测试协议

```bash
python arena.py gomoku_ai.py random_ai.py --board 15 --win 5 --time 5 --games 2
python arena.py gomoku_ai.py random_ai.py --board 9 --win 4 --time 1 --games 2 --quiet
```

## 复现实验

```bash
python benchmark.py --board 9 --win 4 --games 20 --time 0.05
python benchmark.py --board 9 --win 4 --games 4 --time 0.05 --self-play
```

项目仅使用 Python 标准库；不需要安装第三方依赖。
