// Runtime IDs the client makes (api-contract 0): turn_ + ULID for a turn, a UUID for Idempotency-Key and clientMsgId.
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

// 48-bit milliseconds then 80 random bits, Crockford base32 (26 characters, the first one 0-7)
export function ulid(now = Date.now()): string {
  let time = "";
  for (let i = 0, t = now; i < 10; i++, t = Math.floor(t / 32))
    time = CROCKFORD[t % 32] + time;
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let rand = "";
  for (const b of bytes) rand += CROCKFORD[b % 32];
  return time + rand;
}

export const turnId = (): string => `turn_${ulid()}`;

export const uuid = (): string => crypto.randomUUID();
