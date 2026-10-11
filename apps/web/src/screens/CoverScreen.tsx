// 本ごとの入口。家への移動は読みかけの局を変更しない。
import { useQuery } from "@tanstack/react-query";
import { audio } from "../audio";
import { navigate, rolePath } from "../app/router";
import { booksQuery, libraryQuery, manifestFor } from "../app/queries";
import { track } from "../telemetry/telemetry";
import { copy, fill } from "../ui/copy";
import { InAppNotice } from "../ui/InAppNotice";
import { ReadFailed, readFailed } from "../ui/ReadFailed";

export function dayBand(tLabel: string): { day: string; band: string } {
  const [day = tLabel, band = ""] = tLabel.split("・");
  return { day, band };
}

export default function CoverScreen({ bookId }: { bookId: string }) {
  const books = useQuery(booksQuery);
  const book = books.data?.books.find((item) => item.bookId === bookId);
  const manifest = useQuery({
    ...manifestFor(bookId),
    enabled: book?.availability === "available",
  });
  const library = useQuery(libraryQuery);
  const active = library.data?.activePlaythrough;
  const sameBook = active?.bookId === bookId;
  return (
    <main className="screen book-cover">
      <button className="quiet home-back" onClick={() => navigate("/")}>
        ← 書斎に戻る
      </button>
      <InAppNotice />
      <p className="book-author">{book?.author}</p>
      <h1>{book?.title ?? "本をひらいています…"}</h1>
      <p className="note">{book?.description}</p>
      {book?.availability === "available" && (
        <p className="note">
          {copy["cover.note.violence"]}
          <br />
          {copy["cover.note.ai"]}
          <br />
          {copy["cover.note.earphones"]}
        </p>
      )}
      {books.isSuccess && !book && (
        <p className="note">この本は本棚に見つかりませんでした。</p>
      )}
      {book?.availability === "unavailable" && (
        <p className="note">この本は、ただいま支度をしています。</p>
      )}
      {manifest.isSuccess &&
        library.isSuccess &&
        book?.availability === "available" &&
        (sameBook && active ? (
          <>
            <button
              className="primary"
              onClick={() => {
                audio.unlock();
                track("continue_started", {
                  awayMs: Math.max(
                    0,
                    Date.now() - Date.parse(active.updatedAt),
                  ),
                });
                navigate(`/play/${encodeURIComponent(active.playthroughId)}`);
              }}
            >
              {copy["cover.resume"]}
            </button>
            <p className="note">
              {fill(copy["cover.resumeMeta"], {
                role: active.roleName,
                ...dayBand(active.tLabel),
              })}
            </p>
            <button
              className="quiet"
              onClick={() => {
                audio.unlock();
                navigate(rolePath(bookId));
              }}
            >
              {copy["cover.new"]}
            </button>
          </>
        ) : (
          <button
            className="primary"
            onClick={() => {
              audio.unlock();
              navigate(rolePath(bookId));
            }}
          >
            {copy["cover.open"]}
          </button>
        ))}
      {readFailed(books) && <ReadFailed onRetry={() => void books.refetch()} />}
      {readFailed(manifest) && (
        <ReadFailed onRetry={() => void manifest.refetch()} />
      )}
      {readFailed(library) && (
        <ReadFailed onRetry={() => void library.refetch()} />
      )}
    </main>
  );
}
