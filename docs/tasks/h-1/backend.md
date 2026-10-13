# H-1 backend and data: the study, the multi-book catalog, the private gate / H-1 バックエンドとデータ：書斎、複数の本のカタログ、非公開のゲート

## Delivery scope and standards / 納品の範囲と基準

The study is the entrance to the multi-book platform; for now the catalog only opens 『走れメロス』, which has actually been made. A new book must have a world model, scenes, characters, voices and acceptance checks; candidate books, drafts or several versions of the same book must not pass as a playable second book. Returning to the study does not create, abandon or delete any game; continuing progress and recollections are both based on the server's records.

書斎は複数の本を扱うプラットフォームの入口で、現在カタログで公開しているのは実際に制作済みの『走れメロス』だけ。新しい本には世界モデル、シーン、登場人物、音声、受け入れ確認がそろっていなければならず、候補の本、草稿、同じ本の複数バージョンを遊べる 2 冊目と偽ってはならない。書斎に戻っても、どの局も作成・放棄・削除しない。進行の再開も回想も、サーバーの記録を基準とする。

- Added `GET /v1/books` and `GET /v1/library`, with the same shape in the production gateway and the dev mock. The contract generates TypeScript / Python types; they are not copied by hand.
  `GET /v1/books` と `GET /v1/library` を追加し、本番のゲートウェイと開発用 mock で同じ形にした。型は契約から TypeScript / Python で生成し、手で書き写さない。
- The world catalog is read explicitly from `ZJ_WORLD` plus `ZJ_WORLDS`. Each book selects only one version for new games, and all retained old versions can still be restored; reusing the same world version ID across books is rejected.
  世界のカタログは `ZJ_WORLD` と `ZJ_WORLDS` から明示的に読む。本ごとに新しい局用のバージョンは 1 つだけ選び、保持している旧バージョンはすべて引き続き復元できる。複数の本で同じ世界バージョン ID を使い回すことは拒否する。
- The existing rule of one game at a time per account is kept; the multi-book catalog and history are split by book, but this change does not allow several books to be played in parallel games. Only one book is released for now, and the second book used in tests is not used to claim that a second product's content has been made.
  1 アカウントにつき同時に 1 局という既存のルールは維持する。複数の本のカタログと履歴は本ごとに分けるが、今回は複数の本で同時に複数の局を進められるようには変えていない。現在リリースしているのは 1 冊だけで、テスト用の 2 冊目を根拠に 2 冊目の製品コンテンツを制作済みと主張しない。
- Catalog availability comes from the real manifest and the opened identities. Manifests, pre-recorded audio and scene resources are looked up per book. Real voice mode merges each book's voice configuration; if a character ID across books uses a conflicting voice, startup fails, so voices are never mixed.
  カタログの availability は実際の manifest と公開している ID から決まる。manifest、事前収録音声、シーンのリソースは本ごとに参照する。実音声モードは各本の音声設定を統合し、本をまたいだ登場人物 ID が矛盾する音声を使っていれば起動に失敗させ、音声を混ぜない。
- The library queries only for the current session's account. active carries the book and world version; endings require the game to have really ended, the ending to be stored in the database, and the game/version/ending IDs to agree; epilogues not yet stored are listed separately as pending, and records that are unfinished, abandoned or from other accounts are not listed among completed recollections.
  library は現在のセッションのアカウントだけを照会する。active は本と世界バージョンを持つ。endings は、局が実際に終わっていること、エンディングがデータベースに保存されていること、局/バージョン/エンディングの ID が一致することを求める。まだ保存されていないエピローグは pending として別に示し、未完了、放棄済み、他のアカウントの記録は完了した回想に含めない。
- The history list returns only the ending card's title/subtitle; the full ending is still read through the original ending endpoint with an owner check. When a whole game is deleted, the ending is removed by CASCADE and disappears from the very next query.
  履歴の一覧はエンディングカードのタイトル/サブタイトルだけを返す。完全なエンディングは引き続き元の ending のエンドポイントから owner を検証して読む。局全体を削除すると CASCADE でエンディングも削除され、次の照会からすぐに消える。
- Old saves can use `manifest?worldModelVersion=...`; the server verifies that the account really has a game of that version, and an unavailable version returns 404 rather than quietly switching to the current book. Deployments must keep the compatibility resources for old scenes, characters and positions.
  古いセーブは `manifest?worldModelVersion=...` を使える。サーバーはそのアカウントにそのバージョンの局が実際にあるかを確認し、利用できないバージョンには 404 を返し、黙って現在の本に切り替えたりしない。デプロイでは旧シーン、登場人物、立ち位置の互換リソースを残さなければならない。
- When the recollection entry, which has no WebSocket, reads an ending 202, it wakes the existing queue task, reusing the PostgreSQL lease/idempotency protection; a completed result is returned directly without calling the model again.
  WebSocket を持たない回想の入口が ending の 202 を読んだときは既存のキューのタスクを起こし、PostgreSQL のリース/冪等性の保護を再利用する。完了済みの結果はそのまま返し、モデルを再度呼ばない。

## Private access / 非公開アクセス

The outermost ASGI gate covers all pages, scripts, models, textures, scenes, audio, REST and WebSocket; only the empty `/healthz` 204 is exempt. In production, without `ZJ_SITE_PASSWORD`, access is closed with 503; only explicit local dev may run without a password.

最外層の ASGI ゲートは、すべてのページ、スクリプト、モデル、テクスチャ、シーン、音声、REST、WebSocket を覆う。除外するのは空の `/healthz` 204 だけ。本番で `ZJ_SITE_PASSWORD` がなければ 503 でアクセスを閉じ、パスワードなしで動かせるのは明示的なローカルの dev だけ。

The password is injected from the environment / Secret, is at least 16 characters, and never enters logs, URLs, responses or database tables; it is compared in constant time. The pass ticket is HMAC-signed with a random nonce and expires after 12 hours; the cookie uses HttpOnly, Secure in production, and SameSite=Strict. Rotating the password invalidates old tickets. The login form and WS check for a same-origin Origin; each source IP may submit the password at most 10 times per 15 minutes (a bounded in-process counter). After passing, an invite-code account is still needed; the site password is not treated as account permission.

パスワードは環境変数 / Secret から注入し、16 文字以上で、ログ、URL、レスポンス、データベースのテーブルには入れない。比較は定数時間で行う。通行チケットは HMAC で署名し、ランダムな nonce を持ち、12 時間で失効する。cookie は HttpOnly、本番では Secure、SameSite=Strict を使う。パスワードをローテーションすると古いチケットは無効になる。ログインフォームと WS は同一オリジンの Origin を検証する。送信元 IP ごとに 15 分あたり最大 10 回までパスワードを送信できる（プロセス内の上限付きカウンター）。通過した後も招待コードのアカウントが必要で、サイトのパスワードをアカウントの権限とはみなさない。

All private responses are `private, no-store`; when the password is no longer valid, the API returns `X-Site-Access: required` so the frontend can go back to the gate. Success/invalidation requires clearing old browser caches and offline storage, and the frontend also unregisters the old Service Worker. Content that was cached/saved earlier cannot be retroactively withdrawn; local code/tests passing does not mean the old live site has been closed.

非公開のレスポンスはすべて `private, no-store`。パスワードが無効になると API は `X-Site-Access: required` を返し、フロントエンドがゲートに戻れるようにする。成功時/失効時には古いブラウザのキャッシュとオフラインストレージを消す必要があり、フロントエンドは古い Service Worker も登録解除する。以前にキャッシュ/保存された内容は遡って回収できない。ローカルのコードやテストが合格しても、旧本番環境が閉じられたことにはならない。

The deployment script only prepares: the gateway Secret reference, stopping when the password is missing, smoke tests that check the password first and then the invite code, and checking that anonymous assets are refused. `promote` no longer adds allUsers automatically; new services are IAM-private by default, and up/promote/verify choose an identity token based on the real IAM rather than trusting the old OPENED marker. If the privacy lock exists and IAM is public, the script stops; it never deletes the lock. This backend subtask did not perform cloud deployment, model calls or cloud permission writes; tightening access on the live site is handled and verified separately by the overall coordinator.

デプロイスクリプトは準備だけを行う：ゲートウェイの Secret 参照、パスワードがなければ停止、スモークテストはパスワード、次に招待コードの順、匿名アセットが拒否されることの確認。`promote` は allUsers を自動で追加しなくなった。新しいサービスはデフォルトで IAM 非公開で、up/promote/verify は実際の IAM に基づいて ID トークンを選び、古い OPENED マーカーは信用しない。プライバシーロックが存在し IAM が公開になっている場合は停止し、スクリプトがロックを削除することはない。このバックエンドのサブタスクでは、クラウドへのデプロイ、モデルの呼び出し、クラウドの権限の書き込みは行っていない。本番環境でのアクセスの引き締めは全体の調整役が別途処理し検証する。

## Overlapping characters in the stonemason's house / 石工の家での登場人物の重なり

The original `character_spots` put several non-crowd characters at the same point when there were not enough automatic positions. The stonemason's house originally had only two automatic points, so once the player took one, overlap was inevitable.

元の `character_spots` は、自動配置の位置が足りないと複数の群衆でない登場人物を同じ地点に置いていた。石工の家にはもともと自動配置の地点が 2 つしかなく、プレイヤーが 1 つを占めると必ず重なっていた。

8 real flat-ground positions were added, giving 10 automatic points together with the original ones, enough for all 9 non-crowd characters in the current world plus the player; the doorway point reserved for set pieces does not take part in automatic assignment. The new positions avoid walls, door leaves, workbenches and stone blocks, were verified against the existing navmesh for location membership and flat-ground height, and are at least 1.2 m from each other and from the original points.

実際の平地の位置を 8 つ追加し、元の位置と合わせて自動配置の地点を 10 にした。現在の世界の群衆でない登場人物 9 人全員とプレイヤーを収容できる。演出専用の戸口の地点は自動割り当てに参加しない。新しい位置は壁、扉、作業台、石材を避け、既存の navmesh で場所の帰属と平地の高さを検証し、互いにも元の地点からも 1.2 メートル以上離している。

`refresh_spots.mjs` only allows adding flat-ground positions; it verifies the old layout and the hashes of all pipeline inputs, and rejects changes to terrain, existing points or slopes/steps. scene.json is the single runtime source of truth for positions; the runtime was not made to read layout to fill in coordinates. The updated manifest matches the build copied into this working tree, and the geometry, nav, texture and lighting bytes/budgets are unchanged.

`refresh_spots.mjs` は平地の立ち位置の追加だけを許し、旧レイアウトとすべてのパイプライン入力の hash を検証し、地形/既存の地点/坂や段差の変更を拒否する。scene.json が実行時の位置の唯一の正であり、実行時に layout を読んで座標を補うようにはしていない。更新したマニフェストはこの作業ツリーにコピーした build と一致し、ジオメトリ、nav、テクスチャ、ライティングのバイト数/予算は変わっていない。

## Verification record / 検証記録

- Contracts: 507 passed, 6 skipped (the skips are existing generator/sample conditions); includes the new endpoint response types, closed objects and reference validation.
  契約：507 passed、6 skipped（スキップは既存のジェネレーター/サンプルの条件によるもの）。新しいインターフェースのレスポンス型、閉じたオブジェクト、参照の検証を含む。
- Targeted tests for the new features: on real PostgreSQL, the catalog, the second-book test fixture, owner isolation, deletion, switching devices, version locking and recovering a pending epilogue without WS all passed.
  新機能の対象テスト：実際の PostgreSQL で、カタログ、2 冊目のテスト用フィクスチャ、owner の分離、削除、端末の切り替え、バージョンの固定、WS なしでの pending のエピローグの復旧に合格した。
- Real gateway + web_dist: without a pass, pages/JS/scene JSON+GLB/cast/audio/API/WS are refused; after the password, static content is no-store and the API still needs the invite code; after the password and invite code, a real WS welcome is received.
  実際の gateway + web_dist：通行前はページ/JS/scene JSON+GLB/cast/音声/API/WS が拒否される。パスワードの後は静的コンテンツが no-store で、API には引き続き招待コードが必要。パスワードと招待コードの後に実際の WS の welcome を受け取った。
- Gate unit tests: production closed when the password is missing, wrong/expired/forged/rotated tickets, rate limiting, cross-site WS, the Secure cookie and cache headers all passed.
  ゲートの単体テスト：パスワード欠如時の本番の閉鎖、誤り/期限切れ/偽造/ローテーション後のチケット、レート制限、クロスサイトの WS、Secure cookie、キャッシュヘッダーに合格した。
- Scenes: the full check_scene verified the real file hashes and decoded both color tiers successfully; entry 4.79 MB, 19616 triangles and 166 nav polygons did not increase.
  シーン：完全な check_scene で実ファイルの hash を検証し、2 段階の色をデコードして合格した。entry の 4.79 MB、19616 三角形、166 nav polygons はいずれも増えていない。
- `ruff`, `git diff --check` and `bash -n` on the deployment scripts passed.
  `ruff`、`git diff --check`、デプロイスクリプトの `bash -n` に合格した。
- Repo-wide mypy with CI's real extra passed on all 193 files. Three dict invariance errors in the old `test_voice.py` were fixed with explicit type annotations on the test data; the voice runtime logic was not changed.
  CI の real extra を使ったリポジトリ全体の mypy で、193 ファイルすべてが合格した。旧 `test_voice.py` の dict の不変性エラー 3 か所は、テストデータに明示的な型注釈を付けて修正し、音声の実行ロジックは変えていない。
- The final full backend test suite ran completely on the separate database `zoujin_home_test`: 635 passed, 0 failed, 0 skipped, in 728.58 seconds. The first full run caught production/mock manifest cache-header assertions and missing mock coverage of the new endpoints; after fixing them the full run was repeated, and targeted tests were not substituted for the final full result.
  最終的なバックエンド全体のテストは、独立したデータベース `zoujin_home_test` で完全に実行した：635 passed、0 failed、0 skipped、所要 728.58 秒。最初の全量実行で、本番/mock の manifest のキャッシュヘッダーのアサーションと、mock の新エンドポイントのカバー漏れが見つかった。修正後に改めて完全に実行し、対象テストで最終的な全量の結果を代用してはいない。
- The deployment pack check only ignores the top-level generator note `note` (the same road-common is generated by both the village and the return-journey pipelines); validation of files/textures/nested structure/inputs is not loosened; the two diff regressions passed.
  デプロイ用 pack のチェックが無視するのはトップレベルのジェネレーターの説明 `note` だけ（同じ road-common が村と帰路の両方のパイプラインで生成されるため）。ファイル/テクスチャ/入れ子の構造/inputs の検証は緩めていない。差分の回帰テスト 2 件に合格した。
- The overall coordinator's final review found that a failed access-state query was treated as private, the invoker IAM disabled flag was not checked, and DEPLOYED could still be written after the anonymous smoke retries were exhausted; all have been fixed. 15 real Bash control-flow tests verify with a fake gcloud: failures in querying/parsing/tokens stop the script; only a successful empty list can count as a first new service; two public members and the disabled IAM flag are both blocked by the privacy lock; a sixth failure does not continue, and only a sixth success may be marked. The tests read no real configuration and do not access the cloud.
  全体の調整役の最終レビューで、アクセス状態の照会の失敗が非公開として扱われていること、invoker IAM の無効化フラグを確認していないこと、匿名のスモークテストのリトライを使い切っても DEPLOYED を書き込めることが見つかり、いずれも修正した。15 件の実際の Bash 制御フローのテストで偽の gcloud を使って検証した：照会/解析/トークンの失敗で停止する。成功した空のリストだけが初回の新サービスとして扱える。公開メンバー 2 つと IAM の無効化フラグはどちらもプライバシーロックで止まる。6 回目も失敗したら続行せず、6 回目に成功した場合に限りマークできる。テストは実際の設定を読まず、クラウドにもアクセスしない。

## Cross-review and boundaries / クロスレビューと境界

The frontend reported that an old version's manifest might wrongly use the current version; a version parameter and owner check were added, and the frontend has wired Play/Ending to that parameter. The frontend raised the problem of recovering a pending epilogue without WS; idempotent wake-up and a real database regression were added. The backend re-checked the study, Play, Ending and private-state cleanup; the link to the original text is shown only for a book known to correspond to it, and the 『走れメロス』 link is not used for other future books. The backend review found that when the site password expires, WS is refused before accept, so the browser usually only gets 1006; the frontend added a single-flight REST session probe with a 30-second cooldown that relies on the gate header to jump to the password page, plus two regressions, to avoid endless reconnects.

フロントエンドから、旧バージョンの manifest が現在のバージョンを誤って使う可能性があると指摘があり、バージョンのパラメータと owner の検証を追加した。フロントエンドは Play/Ending をそのパラメータにつないだ。フロントエンドが提起した、WS のない pending のエピローグの復旧の問題については、冪等な起動と実データベースの回帰テストを追加した。バックエンドは書斎、Play、Ending、非公開状態の後始末を再確認した。原作へのリンクは対応がわかっている本でだけ表示し、『走れメロス』のリンクを将来の他の本には使わない。バックエンドのレビューで、サイトのパスワードの期限が切れると WS が accept の前に拒否され、ブラウザには通常 1006 しか届かないことがわかった。フロントエンドは single-flight で 30 秒のクールダウンを持つ REST のセッション探査を追加し、ゲートのヘッダーでパスワードページに移動するようにし、回帰テストを 2 件追加して、無限の再接続を防いだ。

This change does not do a production deployment, does not generate a second book's product content, and does not treat dev-mock history as real user endings. Real phone operation, actual model experience and aesthetic acceptance checks continue under the overall acceptance check.

今回は本番のデプロイを行わず、2 冊目の製品コンテンツも生成せず、開発用 mock の履歴を実際のユーザーのエンディングとして扱わない。実際のスマホでの操作、実際のモデルの体験、見た目の受け入れ確認は、全体の受け入れ確認で引き続き行う。

The local dev preview is started with `uv run python infra/deploy/local-preview.py`; the real gateway serves the production build on `127.0.0.1:8091` with the password enforced, and the internal fake-model narrator listens only on loopback `8092`. The separate database `zoujin_home_preview` is not seeded with history; credentials are written only to the 0600 file `~/.zoujin/local-previews/h-1/credentials.json` and do not appear in tool output. `ZJ_DEV=1` is used only for the local HTTP cookie and internal calls; the explicit site password stays enabled.

ローカルの開発プレビューは `uv run python infra/deploy/local-preview.py` で起動する。実際のゲートウェイが `127.0.0.1:8091` で本番ビルドを配信してパスワードを強制し、内部の偽モデルのナレーターはループバックの `8092` だけをリッスンする。独立したデータベース `zoujin_home_preview` には履歴を投入しない。認証情報は 0600 のファイル `~/.zoujin/local-previews/h-1/credentials.json` にだけ書き込み、ツールの出力には出さない。`ZJ_DEV=1` はローカルの HTTP cookie と内部呼び出しにだけ使い、明示的なサイトのパスワードは引き続き有効。
