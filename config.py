import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_token: str
    group_id: int
    db_path: str
    admin_ids: tuple[int, ...]


def _parse_admin_ids(raw: str) -> tuple[int, ...]:
    if not raw:
        return ()
    result = []
    for item in raw.split(","):
        item = item.strip()
        if item:
            result.append(int(item))
    return tuple(result)


def get_settings() -> Settings:
    token = os.getenv("VK_TOKEN", "").strip()
    group_id = os.getenv("GROUP_ID", "").strip()
    db_path = os.getenv("DB_PATH", "dms_navigation.db").strip()
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    if not token:
        raise RuntimeError("Не задан VK_TOKEN. Укажите токен сообщества ВК в .env или переменных окружения.")
    if not group_id:
        raise RuntimeError("Не задан GROUP_ID. Укажите ID сообщества ВК в .env или переменных окружения.")

    return Settings(
        vk_token=token,
        group_id=int(group_id),
        db_path=db_path,
        admin_ids=admin_ids,
    )
