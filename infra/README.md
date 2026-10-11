# infra

云上环境。部署地址、项目 ID、账单 ID、密码不进仓库。后端负责。

`deploy/`：第一版的部署脚本（B-23，gcloud，不用 Terraform），只在 zg 的 Mac 上跑；第 27 步跑 `infra/deploy/deploy.sh all`，见 [deploy/README.md](deploy/README.md)。zg 10-11 起部署不用逐次问（「直接部署」）。

`ci-runner/`：CI 的自建机器（zg 的 Mac 上 Docker 里的 Linux 容器），见 [ci-runner/README.md](ci-runner/README.md)。
