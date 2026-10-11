// the chain-reaction map: a later commit fills it in
export default function ChainMap(p: {
  pid: string;
  names: Record<string, string>;
  eventId?: string;
  why?: string;
}) {
  return p.pid ? null : null;
}
