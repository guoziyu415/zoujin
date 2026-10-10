"""邀请码和会话（B-0 第 3 条、backend-design 5.2）。库里只存邀请码和会话令牌的 sha256。

邀请码：`inv-` 加 4 组、每组 4 个 Crockford base32 字符（80 位随机）。登录时不分大小写，忽略空格和多余的短横线，
I、L 当 1，O 当 0；`inv` 前缀可写可不写。规范化以后再算哈希，所以写法不同的同一个码查得到同一行。
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
SLIDE_AFTER = timedelta(days=1)  # 续期最多一天写一次库
_ALIASES = str.maketrans({"I": "1", "L": "1", "O": "0"})
_SEPARATORS = re.compile(r"[\s\-_]+")


def new_invite_code() -> str:
    n = secrets.randbits(80)
    chars = "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in reversed(range(16)))
    return "inv-" + "-".join(chars[i : i + 4] for i in range(0, 16, 4))


def normalize_invite(code: str) -> str | None:
    """规范写法 `inv-XXXX-XXXX-XXXX-XXXX`；不像邀请码的返回 None。"""
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
    """生成一个邀请码，存它的哈希，返回明文（只给调用方打印一次）。"""
    code = new_invite_code()
    await c.execute(insert(invite_codes).values(code_hash=sha256(code)))
    return code


async def redeem(c: AsyncConnection, ids: IdGen, code: str) -> str | None:
    """邀请码换账号：第一次用时建账号，之后同一个码回到同一个账号。码不对或已作废返回 None。"""
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
    """有效会话的 (userId, 这次续期了没有)。续期：离上次续期超过一天时把过期时间推到 30 天后（滑动）。"""
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
