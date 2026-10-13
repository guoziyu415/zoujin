"""Invite codes and sessions (B-0 item 3, backend-design 5.2). The database stores only the sha256 of invite codes and
session tokens.

Invite code: `inv-` plus 4 groups of 4 Crockford base32 characters (80 random bits). Login is case-insensitive,
ignores spaces and extra hyphens, reads I and L as 1 and O as 0; the `inv` prefix is optional. The hash is computed
after normalizing, so the same code written differently finds the same row.

招待コードとセッション（B-0 第 3 項、backend-design 5.2）。データベースには招待コードとセッショントークンの
sha256 だけを保存する。

招待コード：`inv-` に 4 文字ずつ 4 組の Crockford base32 文字（80 ビットの乱数）。ログイン時は大文字小文字を区別せず、
空白や余分なハイフンを無視し、I と L は 1、O は 0 とみなす。`inv` 接頭辞はあってもなくてもよい。正規化してから
ハッシュを計算するので、書き方が違っても同じコードなら同じ行が見つかる。
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from zoujin_backend.config import SESSION_DAYS
from zoujin_backend.db.tables import invite_codes, sessions, users
from zoujin_backend.ids import CROCKFORD, IdGen

SESSION_TTL = timedelta(days=SESSION_DAYS)
SLIDE_AFTER = timedelta(days=1)  # renewal writes to the DB at most once a day / 延長の DB 書き込みは 1 日 1 回まで
_ALIASES = str.maketrans({"I": "1", "L": "1", "O": "0"})
_SEPARATORS = re.compile(r"[\s\-_]+")


def new_invite_code() -> str:
    n = secrets.randbits(80)
    chars = "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(16)))
    return "inv-" + "-".join(chars[i : i + 4] for i in range(0, 16, 4))


def normalize_invite(code: str) -> str | None:
    """The canonical form `inv-XXXX-XXXX-XXXX-XXXX`; None for anything that doesn't look like an invite code.

    正規形 `inv-XXXX-XXXX-XXXX-XXXX`。招待コードらしくないものは None を返す。
    """
    s = _SEPARATORS.sub("", code).upper()
    s = s.removeprefix("INV")
    s = s.translate(_ALIASES)
    if len(s) != 16 or any(ch not in CROCKFORD for ch in s):
        return None
    return "inv-" + "-".join(s[i : i + 4] for i in range(0, 16, 4))


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def invite_hash(code: str) -> str | None:
    canonical = normalize_invite(code)
    return sha256(canonical) if canonical is not None else None


async def add_invite(c: AsyncConnection) -> str:
    """Generate an invite code, store its hash and return the plaintext (for the caller to print once).

    招待コードを 1 つ生成し、そのハッシュを保存して平文を返す（呼び出し側が 1 回だけ表示する）。
    """
    code = new_invite_code()
    await c.execute(insert(invite_codes).values(code_hash=sha256(code)))
    return code


async def redeem(c: AsyncConnection, ids: IdGen, code: str) -> str | None:
    """Exchange an invite code for an account: the account is created on first use, and later the same code returns to
    the same account. None if the code is wrong or revoked.

    招待コードをアカウントに引き換える：初回使用時にアカウントを作り、以後同じコードは同じアカウントに戻る。
    コードが違うか無効化済みなら None を返す。
    """
    h = invite_hash(code)
    if h is None:
        return None
    row = (
        await c.execute(
            select(invite_codes.c.user_id)
            .where(invite_codes.c.code_hash == h, invite_codes.c.revoked_at.is_(None))
            .with_for_update()
        )
    ).first()
    if row is None:
        return None
    user_id: str | None = row[0]
    now = datetime.now(UTC)
    if user_id is None:
        user_id = ids.new("usr")
        await c.execute(insert(users).values(user_id=user_id, last_login_at=now))
        await c.execute(update(invite_codes).where(invite_codes.c.code_hash == h).values(user_id=user_id))
    else:
        await c.execute(update(users).where(users.c.user_id == user_id).values(last_login_at=now))
    return user_id


async def new_session(c: AsyncConnection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    await c.execute(
        insert(sessions).values(token_hash=sha256(token), user_id=user_id, expires_at=datetime.now(UTC) + SESSION_TTL)
    )
    return token


async def session_user(c: AsyncConnection, token: str | None) -> tuple[str, bool] | None:
    """(userId, whether it was renewed this time) for a valid session. Renewal: when more than a day has passed since
    the last renewal, push the expiry to 30 days from now (sliding).

    有効なセッションの (userId, 今回延長したかどうか)。延長：前回の延長から 1 日以上経っていれば、有効期限を
    今から 30 日後に延ばす（スライディング）。
    """
    if not token:
        return None
    h = sha256(token)
    row = (await c.execute(select(sessions.c.user_id, sessions.c.expires_at).where(sessions.c.token_hash == h))).first()
    now = datetime.now(UTC)
    if row is None or row.expires_at <= now:
        return None
    slid = row.expires_at < now + SESSION_TTL - SLIDE_AFTER
    if slid:
        await c.execute(update(sessions).where(sessions.c.token_hash == h).values(expires_at=now + SESSION_TTL))
    return str(row.user_id), slid


async def end_session(c: AsyncConnection, token: str | None) -> None:
    if token:
        await c.execute(delete(sessions).where(sessions.c.token_hash == sha256(token)))
