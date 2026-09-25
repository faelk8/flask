"""Use cases depend on ports; adapters are injected at the composition root."""
from __future__ import annotations
from typing import Protocol
from .domain import Game, User, NotFound, Unauthorized, ValidationError, game_fields


class GameRepository(Protocol):
    def list(self, page: int, per_page: int) -> tuple[list[Game], int]: ...
    def get(self, game_id: int) -> Game | None: ...
    def cursor(self, after: int, limit: int) -> list[Game]: ...
    def save(self, fields: dict, game_id: int | None = None, **options) -> Game: ...
    def delete(self, game_id: int) -> None: ...


class UserRepository(Protocol):
    def get(self, nickname: str) -> User | None: ...


class PasswordHasher(Protocol):
    def verify(self, password: str, hashed: str) -> bool: ...


class GameService:
    def __init__(self, repository: GameRepository):
        self.repository = repository

    def list(self, page=1, per_page=20):
        try:
            page, per_page = int(page), int(per_page)
        except (ValueError, TypeError):
            raise ValidationError("page e per_page devem ser inteiros.") from None
        if not 1 <= page <= 100000 or not 1 <= per_page <= 100:
            raise ValidationError("page: 1 a 100000; per_page: 1 a 100.")
        games, total = self.repository.list(page, per_page)
        return games, {"page": page, "per_page": per_page, "total": total,
                       "pages": (total + per_page - 1) // per_page}

    def get(self, game_id):
        game = self.repository.get(game_id)
        if game is None:
            raise NotFound("Jogo não encontrado.")
        return game

    def cursor(self, after=0, limit=20):
        try:
            after, limit = int(after), int(limit)
        except (TypeError, ValueError):
            raise ValidationError("after e per_page devem ser inteiros.") from None
        if not 0 <= after <= 2147483647 or not 1 <= limit <= 100:
            raise ValidationError("after: 0 a 2147483647; per_page: 1 a 100.")
        items = self.repository.cursor(after, limit + 1)
        more = len(items) > limit
        return items[:limit], items[limit - 1].id if more else None

    def create(self, data, **options):
        return self.repository.save(game_fields(data), **options)

    def update(self, game_id, data, **options):
        self.get(game_id)
        return self.repository.save(game_fields(data), game_id, **options)

    def delete(self, game_id):
        self.get(game_id)
        self.repository.delete(game_id)


class AuthService:
    def __init__(self, repository: UserRepository, hasher: PasswordHasher, dummy_hash: str):
        self.repository, self.hasher, self.dummy_hash = repository, hasher, dummy_hash

    def authenticate(self, nickname, password):
        if not isinstance(nickname, str) or not isinstance(password, str):
            raise Unauthorized("Credenciais inválidas.")
        if not 1 <= len(nickname) <= 8 or not 1 <= len(password.encode()) <= 72:
            raise Unauthorized("Credenciais inválidas.")
        user = self.repository.get(nickname)
        valid = self.hasher.verify(password, user.password_hash if user else self.dummy_hash)
        if not user or not valid or not user.active:
            raise Unauthorized("Credenciais inválidas.")
        return user
