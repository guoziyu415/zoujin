# infra

Cloud environment. Deployment addresses, project IDs, billing IDs and passwords do not go in the repo. Owned by backend.

クラウド環境。デプロイ先アドレス、プロジェクト ID、請求 ID、パスワードはリポジトリに入れない。バックエンド担当。

`deploy/`: the first-version deployment scripts (B-23, gcloud, no Terraform), run only on zg's Mac; step 27 runs `infra/deploy/deploy.sh all`, see [deploy/README.md](deploy/README.md). Since 10-11, zg no longer needs to be asked for each deployment ("deploy directly").

`deploy/`：第 1 版のデプロイスクリプト（B-23、gcloud、Terraform は使わない）。zg の Mac でのみ実行。ステップ 27 で `infra/deploy/deploy.sh all` を実行する。[deploy/README.md](deploy/README.md) を参照。10-11 以降、zg に毎回確認せずにデプロイしてよい（「直接デプロイ」）。

`ci-runner/`: CI's self-hosted machine (a Linux container in Docker on zg's Mac), see [ci-runner/README.md](ci-runner/README.md).

`ci-runner/`：CI のセルフホストマシン（zg の Mac 上の Docker 内の Linux コンテナ）。[ci-runner/README.md](ci-runner/README.md) を参照。
