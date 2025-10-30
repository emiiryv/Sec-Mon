# migrations/env.py
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# MODELLER
from app.db.models import Base  # target_metadata

# --- .env yükle (proje kökünden) ---
try:
    from dotenv import load_dotenv
    ROOT_DIR = Path(__file__).resolve().parents[1]  # .../Sec-Mon
    DOTENV = ROOT_DIR / ".env"
    load_dotenv(DOTENV, override=False)
except Exception:
    pass

# Alembic Config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 1) Önce ortamdan al
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# 2) Ortam boşsa alembic.ini içindeki sqlalchemy.url'e fallback
if not DATABASE_URL:
    ini_url = config.get_main_option("sqlalchemy.url") or ""
    DATABASE_URL = ini_url

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL tanımlı olmalı (örn: postgresql+asyncpg://user:pass@localhost:5432/secmon)")

# Alembic sync bağlantı ister; asyncpg'yi sync URL'e çevir
sync_url = DATABASE_URL.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")  # zaten sync_url set edildi
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # mevcut config'e senkron URL'i yaz
    sync_url = config.get_main_option("sqlalchemy.url")

    # alembic section'ı al, yoksa boş dict ver
    section = config.get_section(config.config_ini_section) or {}
    # prefix='sqlalchemy.' kullanacağımız için anahtarın adı 'sqlalchemy.url' olmalı
    section["sqlalchemy.url"] = sync_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",          # <--- kritik düzeltme
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()