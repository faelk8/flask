from app.application import GameService
from app.domain import Game, ValidationError
import pytest


class MemoryRepository:
    def __init__(self):
        self.saved = None

    def save(self, fields, game_id=None):
        self.saved = Game(game_id or 1, **fields)
        return self.saved


def test_use_case_with_injected_repository_without_flask():
    repository = MemoryRepository()
    service = GameService(repository)
    game = service.create({'nome': '  Tetris  ', 'categoria': 'Puzzle', 'console': 'PC'})
    assert game.nome == 'Tetris'
    assert repository.saved == game


def test_invalid_data_does_not_reach_persistence():
    repository = MemoryRepository()
    with pytest.raises(ValidationError):
        GameService(repository).create({'nome': ''})
    assert repository.saved is None
