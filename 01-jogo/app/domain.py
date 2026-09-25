"""Business entities and errors; no Flask or persistence dependencies."""
from dataclasses import dataclass


class DomainError(Exception):
    pass


class ValidationError(DomainError):
    pass


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass


class Forbidden(DomainError):
    pass


class QuotaExceeded(DomainError):
    pass


class Unauthorized(DomainError):
    pass


@dataclass(frozen=True)
class Game:
    id: int
    nome: str
    categoria: str
    console: str


@dataclass(frozen=True)
class User:
    nickname: str
    password_hash: str
    role: str = "viewer"
    active: bool = True
    mfa_enabled: bool = False


def game_fields(data):
    if not isinstance(data, dict):
        raise ValidationError("Envie um objeto com nome, categoria e console.")
    if set(data) != {"nome", "categoria", "console"}:
        raise ValidationError("Campos permitidos e obrigatórios: nome, categoria, console.")
    result = {}
    for field, limit in (("nome", 50), ("categoria", 40), ("console", 20)):
        value = data[field]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
            raise ValidationError(f"{field} deve conter entre 1 e {limit} caracteres.")
        result[field] = value.strip()
    return result
