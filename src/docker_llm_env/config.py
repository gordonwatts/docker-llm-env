from pathlib import Path

from dotenv import dotenv_values


def load_config() -> dict:
    dotfile = Path.home() / ".docker-llm-env"
    if not dotfile.exists():
        raise SystemExit(
            f"\nConfig file not found: {dotfile}\n\n"
            "Create it with your GitHub personal access token:\n\n"
            "    echo 'GITHUB_TOKEN=ghp_your_token_here' > ~/.docker-llm-env\n"
            "    chmod 600 ~/.docker-llm-env\n\n"
            "Get a token at: https://github.com/settings/tokens\n"
            "Required scopes: repo (for forking and pushing branches)\n"
        )

    config = dotenv_values(dotfile)
    if not config.get("GITHUB_TOKEN"):
        raise SystemExit(
            "\nGITHUB_TOKEN not set in ~/.docker-llm-env\n\n"
            "Add it:\n"
            "    echo 'GITHUB_TOKEN=ghp_your_token_here' >> ~/.docker-llm-env\n"
        )

    return config
