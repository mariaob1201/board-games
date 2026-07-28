"""Two GPT personas play chess against each other.

python-chess owns the board and enforces legality; each persona only
ever chooses among the legal moves it's handed. Output is a PGN file
and a JSON move log (FEN + commentary per ply) for replay.
"""
import json
import random
import re
from pathlib import Path

import chess
import chess.pgn
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = "gpt-5"
MAX_COMPLETION_TOKENS = 400
REASONING_EFFORT = "minimal"  # gpt-5 defaults to heavy reasoning that can consume
                               # the whole token budget with zero visible output
MAX_PLIES = 80
MAX_RETRIES = 3

PERSONAS = {
    chess.WHITE: {
        "name": "The Aggressor",
        "system": (
            "You are 'The Aggressor', a swashbuckling chess player who loves "
            "sharp tactics, sacrifices, and direct attacks on the enemy king. "
            "You favor initiative over material. You are playing WHITE."
        ),
    },
    chess.BLACK: {
        "name": "The Strategist",
        "system": (
            "You are 'The Strategist', a patient, positional chess player who "
            "values pawn structure, piece coordination, and long-term "
            "advantages over immediate complications. You are playing BLACK."
        ),
    },
}

client = OpenAI()


def legal_san_moves(board: chess.Board) -> list[str]:
    return [board.san(m) for m in board.legal_moves]


def ask_move(board: chess.Board, color: bool, history_san: list[str], 
             feedback: str = "") -> tuple[str, str]:
    persona = PERSONAS[color]
    legal = legal_san_moves(board)
    move_no = board.fullmove_number
    history_str = " ".join(history_san) if history_san else "(none yet)"

    user_msg = (
        f"Position (FEN): {board.fen()}\n"
        f"Move history (SAN): {history_str}\n"
        f"It is move {move_no}, {'White' if color == chess.WHITE else 'Black'} to play.\n"
        f"Legal moves: {', '.join(legal)}\n\n"
        f"{feedback}"
        "Choose exactly one move from the legal moves list. "
        'Respond with ONLY a JSON object on a single line: '
        '{\"move\": \"<SAN move exactly as listed>\", \"comment\": \"<one short in-character sentence>\"}'
    )

    resp = client.chat.completions.create(
        model=MODEL,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        messages=[
            {"role": "system", "content": persona["system"]},
            {"role": "user", "content": user_msg},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return "", text[:200]
    try:
        data = json.loads(match.group(0))
        return data.get("move", "").strip(), data.get("comment", "").strip()
    except json.JSONDecodeError:
        return "", text[:200]


def play_game() -> dict:
    board = chess.Board()
    history_san: list[str] = []
    log = []

    while not board.is_game_over(claim_draw=True) and len(history_san) < MAX_PLIES:
        color = board.turn
        legal = legal_san_moves(board)
        feedback = ""
        move_san, comment, fallback = None, "", False

        for attempt in range(MAX_RETRIES):
            candidate_san, candidate_comment = ask_move(board, color, history_san, feedback)
            if candidate_san in legal:
                move_san, comment = candidate_san, candidate_comment
                break
            feedback = f'Your previous reply "{candidate_san}" was not a legal move. '
        else:
            move_san = random.choice(legal)
            comment = "(fallback: random legal move after invalid replies)"
            fallback = True

        move = board.parse_san(move_san)
        fen_before = board.fen()
        board.push(move)
        history_san.append(move_san)

        print(f"{len(history_san):>3}. {'W' if color else 'B'} {move_san:<8} "
              f"{'[fallback] ' if fallback else ''}{comment}")

        log.append({
            "ply": len(history_san),
            "color": "white" if color == chess.WHITE else "black",
            "persona": PERSONAS[color]["name"],
            "san": move_san,
            "fen_before": fen_before,
            "fen_after": board.fen(),
            "comment": comment,
            "fallback": fallback,
        })

    result = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "*"

    game = chess.pgn.Game()
    game.headers["Event"] = "LLM Chess Duel"
    game.headers["White"] = PERSONAS[chess.WHITE]["name"]
    game.headers["Black"] = PERSONAS[chess.BLACK]["name"]
    game.headers["Result"] = result
    node = game
    replay = chess.Board()
    for entry in log:
        mv = replay.parse_san(entry["san"])
        node = node.add_variation(mv)
        if entry["comment"]:
            node.comment = entry["comment"]
        replay.push(mv)

    return {
        "result": result,
        "termination": board.outcome(claim_draw=True).termination.name if board.outcome(claim_draw=True) else "MAX_PLIES",
        "log": log,
        "pgn": str(game),
    }


if __name__ == "__main__":
    out_dir = Path(__file__).parent / "games"
    out_dir.mkdir(exist_ok=True)

    data = play_game()

    (out_dir / "game_001.json").write_text(json.dumps({
        "white": PERSONAS[chess.WHITE]["name"],
        "black": PERSONAS[chess.BLACK]["name"],
        "result": data["result"],
        "termination": data["termination"],
        "moves": data["log"],
    }, indent=2))
    (out_dir / "game_001.pgn").write_text(data["pgn"])

    print(f"\nResult: {data['result']} ({data['termination']})")
    print(f"Saved to {out_dir}/game_001.json and game_001.pgn")
