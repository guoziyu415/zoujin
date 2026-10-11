// 书房是书籍目录与真实存档的入口。这里的任何操作都不创建、删除或重置一局。
import type { Api } from "@zoujin/contracts";
import { useQuery } from "@tanstack/react-query";
import {
  Component,
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { flags } from "../app/flags";
import { booksQuery, libraryQuery } from "../app/queries";
import { bookPath, navigate } from "../app/router";
import { audio } from "../audio";
import { track } from "../telemetry/telemetry";
import { InAppNotice } from "../ui/InAppNotice";
import { ReadFailed, readFailed } from "../ui/ReadFailed";
import "../ui/home.css";

const HomeScene = lazy(() => import("../three/home/HomeScene"));
type Panel = "books" | "memories" | null;

export default function HomeScreen() {
  const books = useQuery(booksQuery);
  const library = useQuery(libraryQuery);
  const [panel, setPanel] = useState<Panel>(null);
  const active = library.data?.activePlaythrough;
  const activeBook = books.data?.books.find(
    (book) => book.bookId === active?.bookId,
  );
  const endings = library.data?.endings ?? [];
  const pending = library.data?.pendingEndings ?? [];

  return (
    <main className="reader-home">
      <div className="home-scene" aria-hidden="true">
        {!flags.no3d && library.isSuccess && (
          <SceneBoundary>
            <Suspense
              fallback={
                <div className="home-scene-loading" role="presentation" />
              }
            >
              <HomeScene
                onSelectBook={() => setPanel("books")}
                onOpenMemories={() => setPanel("memories")}
                focus={panel ?? "room"}
              />
            </Suspense>
          </SceneBoundary>
        )}
      </div>
      <header className="home-header">
        <a className="home-brand" href="/" aria-label="zoujin ホーム">
          zoujin<span>走 進</span>
        </a>
        <p>物語と、あなたのあいだ。</p>
        <span className="home-invite">18歳以上・招待制</span>
      </header>
      <div className="home-welcome">
        <p className="home-eyebrow">物語がはじまる場所</p>
        <h1>あなたの書斎</h1>
        <p>
          一冊をひらく。
          <br />
          その世界を、生きてみる。
        </p>
      </div>
      <footer className="home-controls">
        <InAppNotice />
        {active && (
          <button className="home-resume" onClick={() => resume(active)}>
            <span className="home-resume-mark" aria-hidden="true">
              ▤
            </span>
            <span>
              <small>しおりの続きから</small>
              <strong>{activeBook?.title ?? "読みかけの物語"}</strong>
              <span>
                {active.roleName} · {active.tLabel}
              </span>
            </span>
            <span aria-hidden="true">→</span>
          </button>
        )}
        {readFailed(library) && (
          <div className="home-load-error">
            <ReadFailed onRetry={() => void library.refetch()} />
          </div>
        )}
        <nav className="home-destinations" aria-label="書斎でできること">
          <button onClick={() => setPanel("books")}>
            <span className="home-nav-number">01</span>
            <span>
              <strong>本棚</strong>
              <small>次の世界を選ぶ</small>
            </span>
            <span aria-hidden="true">↗</span>
          </button>
          <button onClick={() => setPanel("memories")}>
            <span className="home-nav-number">02</span>
            <span>
              <strong>回想録</strong>
              <small>たどり着いた結末</small>
            </span>
            <span aria-hidden="true">↗</span>
          </button>
        </nav>
        <p className="home-caption">本棚と机の上の回想録からも、ひらけます。</p>
      </footer>
      {panel && (
        <HomePanel
          title={panel === "books" ? "本棚" : "回想録"}
          eyebrow={
            panel === "books" ? "次にひらく、一冊" : "あなたが生きた物語"
          }
          onClose={() => setPanel(null)}
        >
          {panel === "books" ? (
            <>
              <p className="home-panel-lead">次は、どの世界へ。</p>
              {books.isPending && (
                <p role="status" className="home-muted">
                  本を並べています…
                </p>
              )}
              {readFailed(books) && (
                <ReadFailed onRetry={() => void books.refetch()} />
              )}
              <div className="home-book-list">
                {books.data?.books.map((book) => (
                  <Book
                    key={book.bookId}
                    book={book}
                    active={active?.bookId === book.bookId}
                  />
                ))}
              </div>
              {books.isSuccess && books.data.books.length === 0 && (
                <p className="home-empty">
                  本の支度をしています。しばらくしてから、もう一度お越しください。
                </p>
              )}
              <p className="home-panel-footnote">
                ここは、いくつもの物語へつながる書斎。
                <br />
                新しい本は、支度が整い次第、本棚に並びます。
              </p>
            </>
          ) : (
            <>
              <p className="home-panel-lead">
                あなたが生きた物語を、もう一度。
              </p>
              {library.isPending && (
                <p role="status" className="home-muted">
                  回想録をひらいています…
                </p>
              )}
              {readFailed(library) && (
                <ReadFailed onRetry={() => void library.refetch()} />
              )}
              {library.isSuccess &&
                endings.length === 0 &&
                pending.length === 0 && (
                  <div className="home-empty">
                    <span aria-hidden="true">—</span>
                    <h3>まだ、白いページ。</h3>
                    <p>
                      物語の終わりにたどり着くと、
                      <br />
                      あなたの結末がここに残ります。
                    </p>
                    <button
                      className="home-text-button"
                      onClick={() => setPanel("books")}
                    >
                      本棚へ →
                    </button>
                  </div>
                )}
              <ol className="home-memory-list">
                {pending.map((memory) => (
                  <li key={memory.playthroughId}>
                    <button
                      onClick={() =>
                        navigate(
                          `/ending/${encodeURIComponent(memory.playthroughId)}`,
                        )
                      }
                    >
                      <small>
                        {memory.bookTitle} · {memory.roleName}
                      </small>
                      <strong>物語を綴じています</strong>
                      <span>結末の続きを受け取る →</span>
                    </button>
                  </li>
                ))}
                {endings.map((memory) => (
                  <li key={memory.playthroughId}>
                    <button
                      onClick={() =>
                        navigate(
                          `/ending/${encodeURIComponent(memory.playthroughId)}`,
                        )
                      }
                    >
                      <small>
                        {memory.bookTitle} · {memory.roleName}
                      </small>
                      <strong>{memory.title}</strong>
                      {memory.subtitle && <span>{memory.subtitle}</span>}
                      <time dateTime={memory.endedAt}>
                        {memoryDate(memory.endedAt)}
                      </time>
                      <span className="home-memory-open">この結末を読む →</span>
                    </button>
                  </li>
                ))}
              </ol>
            </>
          )}
        </HomePanel>
      )}
    </main>
  );
}

function resume(active: Api.LibraryResponse["activePlaythrough"] & {}) {
  audio.unlock();
  track("continue_started", {
    awayMs: Math.max(0, Date.now() - Date.parse(active.updatedAt)),
  });
  navigate(`/play/${encodeURIComponent(active.playthroughId)}`);
}

function Book({
  book,
  active,
}: {
  book: Api.BooksResponse["books"][number];
  active: boolean;
}) {
  const available = book.availability === "available";
  return (
    <article className="home-book">
      <div className="home-book-jacket" aria-hidden="true">
        <span>{book.author}</span>
        <strong>{book.title}</strong>
        <i>zoujin</i>
      </div>
      <div className="home-book-info">
        <span className="home-book-status">
          {active ? "しおりを挟んだ本" : available ? "ひらける物語" : "準備中"}
        </span>
        <h3>{book.title}</h3>
        <p className="home-book-author">
          {book.author}
          {book.year ? ` · ${book.year}` : ""}
        </p>
        <p>{book.description}</p>
        <button
          className="home-book-open"
          disabled={!available}
          onClick={() => navigate(bookPath(book.bookId))}
        >
          {available ? "この本をひらく" : "もうしばらくお待ちください"}
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </article>
  );
}

// Native dialog supplies modal focus containment, Escape, inert background and focus restoration.
function HomePanel({
  title,
  eyebrow,
  onClose,
  children,
}: {
  title: string;
  eyebrow: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const node = dialog.current;
    node?.showModal();
    return () => node?.close();
  }, []);
  useEffect(() => {
    close.current?.focus();
  }, [title]);
  return (
    <dialog
      ref={dialog}
      className="home-panel"
      aria-labelledby="home-panel-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect();
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose();
        }
      }}
    >
      <div className="home-panel-inner">
        <header>
          <div>
            <p className="home-eyebrow">{eyebrow}</p>
            <h2 id="home-panel-title">{title}</h2>
          </div>
          <button
            ref={close}
            className="home-panel-close"
            onClick={onClose}
            autoFocus
            aria-label="書斎に戻る"
          >
            ×
          </button>
        </header>
        {children}
      </div>
    </dialog>
  );
}

class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override render() {
    return this.state.failed ? (
      <div className="home-scene-loading" />
    ) : (
      this.props.children
    );
  }
}

function memoryDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : new Intl.DateTimeFormat("ja-JP", {
        year: "numeric",
        month: "long",
        day: "numeric",
      }).format(date);
}
