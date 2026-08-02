"""Аналитика: рейтинги команд, симуляции турнира, проекции игроков."""

from .glicko2 import GameResult, Glicko2, Rating

__all__ = ["GameResult", "Glicko2", "Rating"]
