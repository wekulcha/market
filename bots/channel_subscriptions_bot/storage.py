import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram.types import Chat, User


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS owners (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registered_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channels (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    username TEXT,
                    owner_user_id INTEGER NOT NULL,
                    bot_status TEXT NOT NULL,
                    bound_at TEXT NOT NULL,
                    FOREIGN KEY(owner_user_id) REFERENCES owners(user_id)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    event_type TEXT NOT NULL,
                    old_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    event_time_utc TEXT NOT NULL,
                    actor_user_id INTEGER
                );
                """
            )

    def upsert_owner(self, user: User) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO owners (user_id, username, first_name, last_name, registered_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name
                """,
                (
                    user.id,
                    user.username,
                    user.first_name,
                    user.last_name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def owner_exists(self, user_id: int) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM owners WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row is not None

    def bind_channel(self, chat: Chat, owner_user_id: int, bot_status: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO channels (chat_id, title, username, owner_user_id, bot_status, bound_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = excluded.title,
                    username = excluded.username,
                    owner_user_id = excluded.owner_user_id,
                    bot_status = excluded.bot_status
                """,
                (
                    chat.id,
                    chat.title,
                    chat.username,
                    owner_user_id,
                    bot_status,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def unbind_channel(self, chat_id: int) -> int | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT owner_user_id FROM channels WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            connection.execute("DELETE FROM channels WHERE chat_id = ?", (chat_id,))
            return int(row["owner_user_id"]) if row else None

    def get_channel_owner(self, chat_id: int) -> int | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT owner_user_id FROM channels WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            return int(row["owner_user_id"]) if row else None

    def list_channels_for_owner(self, owner_user_id: int) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT chat_id, title, username, bound_at
                FROM channels
                WHERE owner_user_id = ?
                ORDER BY bound_at DESC
                """,
                (owner_user_id,),
            ).fetchall()

    def list_known_users(self) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                WITH seen AS (
                    SELECT
                        user_id,
                        username,
                        trim(coalesce(first_name, '') || ' ' || coalesce(last_name, '')) AS full_name,
                        registered_at AS seen_at
                    FROM owners
                    UNION ALL
                    SELECT
                        user_id,
                        username,
                        full_name,
                        event_time_utc AS seen_at
                    FROM events
                ),
                seen_range AS (
                    SELECT user_id, min(seen_at) AS first_seen, max(seen_at) AS last_seen
                    FROM seen
                    GROUP BY user_id
                ),
                latest_events AS (
                    SELECT e.user_id, e.event_type, e.event_time_utc
                    FROM events e
                    JOIN (
                        SELECT user_id, max(id) AS max_id
                        FROM events
                        GROUP BY user_id
                    ) latest ON latest.max_id = e.id
                ),
                active_subscriptions AS (
                    SELECT e.user_id, count(*) AS active_subscriptions_count
                    FROM events e
                    JOIN (
                        SELECT user_id, chat_id, max(id) AS max_id
                        FROM events
                        GROUP BY user_id, chat_id
                    ) latest ON latest.max_id = e.id
                    WHERE e.event_type = 'subscribe'
                    GROUP BY e.user_id
                )
                SELECT
                    seen_range.user_id,
                    coalesce((
                        SELECT username
                        FROM seen s
                        WHERE s.user_id = seen_range.user_id
                          AND username IS NOT NULL
                          AND username != ''
                        ORDER BY seen_at DESC
                        LIMIT 1
                    ), '') AS username,
                    coalesce((
                        SELECT full_name
                        FROM seen s
                        WHERE s.user_id = seen_range.user_id
                          AND full_name IS NOT NULL
                          AND full_name != ''
                        ORDER BY seen_at DESC
                        LIMIT 1
                    ), '') AS full_name,
                    seen_range.first_seen,
                    seen_range.last_seen,
                    CASE
                        WHEN owners.user_id IS NULL THEN 0
                        ELSE 1
                    END AS is_owner,
                    coalesce((
                        SELECT count(*)
                        FROM events e
                        WHERE e.user_id = seen_range.user_id
                    ), 0) AS events_count,
                    coalesce(active_subscriptions.active_subscriptions_count, 0) AS active_subscriptions_count,
                    latest_events.event_type AS last_event_type,
                    latest_events.event_time_utc AS last_event_time
                FROM seen_range
                LEFT JOIN owners ON owners.user_id = seen_range.user_id
                LEFT JOIN latest_events ON latest_events.user_id = seen_range.user_id
                LEFT JOIN active_subscriptions ON active_subscriptions.user_id = seen_range.user_id
                ORDER BY seen_range.last_seen DESC
                """
            ).fetchall()

    def get_known_user(self, user_id: int) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                """
                WITH seen AS (
                    SELECT
                        user_id,
                        username,
                        trim(coalesce(first_name, '') || ' ' || coalesce(last_name, '')) AS full_name,
                        registered_at AS seen_at
                    FROM owners
                    WHERE user_id = ?
                    UNION ALL
                    SELECT
                        user_id,
                        username,
                        full_name,
                        event_time_utc AS seen_at
                    FROM events
                    WHERE user_id = ?
                )
                SELECT
                    user_id,
                    coalesce((
                        SELECT username
                        FROM seen s
                        WHERE username IS NOT NULL AND username != ''
                        ORDER BY seen_at DESC
                        LIMIT 1
                    ), '') AS username,
                    coalesce((
                        SELECT full_name
                        FROM seen s
                        WHERE full_name IS NOT NULL AND full_name != ''
                        ORDER BY seen_at DESC
                        LIMIT 1
                    ), '') AS full_name,
                    min(seen_at) AS first_seen,
                    max(seen_at) AS last_seen
                FROM seen
                GROUP BY user_id
                """,
                (user_id, user_id),
            ).fetchone()

    def list_user_subscriptions(self, user_id: int) -> list[sqlite3.Row]:
        with self.connect() as connection:
            return connection.execute(
                """
                SELECT
                    e.chat_id,
                    channels.title,
                    channels.username,
                    e.event_time_utc AS subscribed_at,
                    e.old_status,
                    e.new_status
                FROM events e
                JOIN (
                    SELECT chat_id, max(id) AS max_id
                    FROM events
                    WHERE user_id = ?
                    GROUP BY chat_id
                ) latest ON latest.max_id = e.id
                LEFT JOIN channels ON channels.chat_id = e.chat_id
                WHERE e.event_type = 'subscribe'
                ORDER BY e.event_time_utc DESC
                """,
                (user_id,),
            ).fetchall()

    def record_event(
        self,
        chat_id: int,
        user: User,
        event_type: str,
        old_status: str,
        new_status: str,
        event_time: datetime,
        actor_user_id: int | None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events (
                    chat_id,
                    user_id,
                    username,
                    full_name,
                    event_type,
                    old_status,
                    new_status,
                    event_time_utc,
                    actor_user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user.id,
                    user.username,
                    " ".join(part for part in [user.first_name, user.last_name] if part),
                    event_type,
                    old_status,
                    new_status,
                    event_time.isoformat(),
                    actor_user_id,
                ),
            )
