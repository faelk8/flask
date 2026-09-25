"""Compatibility entrypoint: delegates to the non-destructive development command."""
from app import create_app

if __name__ == "__main__":
    app = create_app()
    result = app.test_cli_runner().invoke(args=["init-db"])
    print(result.output, end="")
    raise SystemExit(result.exit_code)
