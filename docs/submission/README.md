# 物語 (Monogatari) Submission Materials / 提出資料

This directory provides the project text and architecture image for the 5th Agentic AI Hackathon. The product concept, descriptions, images and video may be made public, the actual app stays password-protected, and the repository stays private. Recording the video and uploading it to YouTube is done by the user.

このディレクトリは第5回 Agentic AI Hackathon のプロジェクト文章とアーキテクチャ画像を提供する。プロダクトコンセプト、説明、画像、動画は公開してよく、実際のアプリはパスワード付きのまま、リポジトリは非公開のままとする。動画の録画と YouTube へのアップロードはユーザーが行う。

## Form mapping / フォーム対応

| Submission field / 提出項目 | Material to use / 使用する資料 |
| --- | --- |
| Project name / プロジェクト名 | [project-title-ja.txt](project-title-ja.txt) |
| Summary (if the form has this field) / 概要（フォームにある場合） | [short-description-ja.txt](short-description-ja.txt) |
| Users, problem, solution and features / ユーザー、課題、解決策と特徴 | [project-description-ja.txt](project-description-ja.txt) can be copied directly; the [Markdown version](project-description-ja.md) is for reading and editing / [project-description-ja.txt](project-description-ja.txt) はそのままコピーできる。[Markdown 版](project-description-ja.md) は閲覧と編集用 |
| System architecture diagram / システム構成図 | [architecture.png](architecture.png), 1920×1080; [architecture.svg](architecture.svg) is the editable source / [architecture.png](architecture.png)（1920×1080）。[architecture.svg](architecture.svg) は編集可能なソース |
| Demo video / デモ動画 | Recorded by the user and uploaded publicly to YouTube; enter the actual video link / ユーザーが録画して YouTube に公開アップロードし、実際の動画リンクを入力する |
| Video title and description / 動画のタイトルと説明 | [youtube-metadata-ja.txt](youtube-metadata-ja.txt) |
| Private GitHub repository / 非公開 GitHub リポジトリ | Connect the existing private repository with the GitHub App in the event dashboard, granting only the permissions that repository needs / 大会の管理画面で GitHub App により既存の非公開リポジトリを接続し、そのリポジトリに必要な権限だけを付与する |
| Deployment URL, 動作確認の方法 | Use the review instructions kept privately on this machine; this directory contains no URL, password or invite code / この端末に非公開で保管した審査用の説明を使う。このディレクトリには URL、パスワード、招待コードを含めない |

The [official conditions](https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5) allow private repositories and deployments that require authentication, but reviewers must be given an account and samples that need no social login or email receipt. After the official submission, the default branch and a working deployment are kept until December 1; further development goes on other branches.

[公式の条件](https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5)は非公開リポジトリと認証が必要なデプロイを認めているが、審査員にはソーシャルログインやメール受信が不要なアカウントとサンプルを提供する必要がある。正式提出後、デフォルトブランチと利用可能なデプロイは 12 月 1 日まで維持し、以降の開発は別ブランチで行う。

## Recording and judging basis / 録画と審査の根拠

- [demo-script-ja.md](demo-script-ja.md): about 3 minutes of shots, captions and Japanese narration; adjustable to actual results.
  [demo-script-ja.md](demo-script-ja.md)：約 3 分のカット、字幕、日本語ナレーション。実際の結果に合わせて調整できる。
- [recording-checklist-zh.md](recording-checklist-zh.md): operating points for starting to record right away.
  [recording-checklist-zh.md](recording-checklist-zh.md)：すぐに録画を始めるための操作要点。
- [evidence-and-judging-ja.md](evidence-and-judging-ja.md): Agency for Cultural Affairs statistics, UNESCO policy background, the mapping to the three scoring criteria, and the limits of verification.
  [evidence-and-judging-ja.md](evidence-and-judging-ja.md)：文化庁の統計、UNESCO の政策的背景、3 つの評価項目との対応、検証の限界。

The project's claim is that adults enter a literary world and interact with characters who remember them, finally forming three layers of endings: world, characters and player. Official materials support the problem background and the direction of cultural learning; they do not prove that this project has increased reading volume, empathy or academic performance. Currently only one book is actually included, and we do not advertise that other works are playable.

プロジェクトの主張は、大人が文学の世界に入り、自分を覚えている人物と影響し合い、最終的に世界、人物、プレイヤーの三層の結末が形づくられること。公式資料は課題の背景と文化学習の方向性を裏付けるが、本プロジェクトが読書量、共感、学業成績を向上させたことを証明するものではない。現在実際に収録しているのは 1 冊だけで、他の作品が遊べるとは宣伝しない。

## Final checks before submission / 提出前の最終確認

1. Event registration status, member conditions and the GitHub App connection are all checked in your own event dashboard; finished materials do not mean the official submission is complete.
   大会の登録状態、メンバー条件、GitHub App の接続はすべてご自身の大会管理画面で確認する。資料が完成していても正式提出が完了したことにはならない。
2. The video shows your own actual operation, and character replies, events and endings are not faked; different save data and skipped waiting must be stated.
   動画はご自身の実際の操作で、人物の返答、イベント、結末を偽造しない。セーブデータが異なる場合や待ち時間を省略した場合は明記する。
3. The public description, images, video and YouTube description contain no deployment address, invite code, password, personal cloud project ID or real user data.
   公開する説明、画像、動画、YouTube の説明に、デプロイ先アドレス、招待コード、パスワード、個人のクラウドプロジェクト ID、実在ユーザーのデータを含めない。
4. The review deployment URL, password, main invite code and backup invite code are placed only in the private 「動作確認の方法」 and are not pasted into the public description.
   審査用のデプロイ URL、パスワード、メイン招待コード、予備の招待コードは非公開の「動作確認の方法」にのみ置き、公開の説明には貼らない。
5. The architecture diagram and the Japanese description use the current implementation: Gemini handles character voice and text replies, and Claude handles narration and other processing; the old Firestore, ADK or Veo plans are not carried over.
   アーキテクチャ図と日本語の説明は現在の実装に従う：Gemini が人物の音声とテキスト返答を担当し、Claude がナレーションなどの処理を担当する。古い Firestore、ADK、Veo の案は持ち込まない。
6. Enter the URL of the video that actually uploaded successfully, save, and check the final submission confirmation; do not treat a saved draft or a file selection as submitted.
   実際にアップロードに成功した動画の URL を入力し、保存して最終提出の確認を確かめる。下書き保存やファイル選択を提出済みとみなさない。

The architecture diagram was checked by two roles and visually inspected. The latest code still has the observed risks of missing answers and templated endings; the 200 runs and the remaining CI were skipped by the user's decision. This change only adds submission materials and does not change the live program or remove the password.

アーキテクチャ図は 2 つのロールで確認し、目視でも検査した。最新のコードには、観測済みの回答の欠落とテンプレート的な結末のリスクが残っている。200 プレイと残りの CI はユーザーの判断で省略した。今回は提出資料を補っただけで、オンラインのプログラムは変更せず、パスワードも外していない。

## Regenerating the architecture diagram / アーキテクチャ図の再生成

Use a Python environment with Pillow and run `build_visuals.py --font <Japanese font file>`. The PNG and SVG are generated from the same coordinates, text and connections; the diagram shows only the main call paths, and the gateway also calls Claude for safety checks and candidate generation.

Pillow のある Python 環境で `build_visuals.py --font <日本語フォントファイル>` を実行する。PNG と SVG は同じ座標、文字、接続線から生成する。図は主な呼び出し経路だけを示し、ゲートウェイは安全性チェックと候補生成のためにも Claude を呼び出す。
