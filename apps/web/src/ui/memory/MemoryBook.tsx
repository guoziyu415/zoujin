// the memory book: the next commit fills it in
export default function MemoryBook(p: {
  pid: string;
  names: Record<string, string>;
  start?: string | undefined;
}) {
  return p.pid ? null : null;
}
