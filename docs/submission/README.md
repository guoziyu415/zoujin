# zoujin 提交材料

本目录提供第5回 Agentic AI Hackathon 的项目文字和架构图片。产品概念、说明、图和视频允许公开，实际应用继续带密码，仓库保持私有。视频录制和 YouTube 上传由用户完成。

## 表单对应

| 提交字段 | 使用材料 |
| --- | --- |
| 项目名 | [project-title-ja.txt](project-title-ja.txt) |
| 简介（如果表单有此字段） | [short-description-ja.txt](short-description-ja.txt) |
| 用户、问题、解决方案与特点 | [project-description-ja.txt](project-description-ja.txt) 可直接复制；[Markdown版](project-description-ja.md) 用于阅读和修改 |
| 系统架构图 | [architecture.png](architecture.png)，1920×1080；[architecture.svg](architecture.svg) 为可编辑源稿 |
| 演示视频 | 用户录制并公开上传 YouTube，填实际视频链接 |
| 视频标题与说明 | [youtube-metadata-ja.txt](youtube-metadata-ja.txt) |
| 私有 GitHub 仓库 | 在赛事后台用 GitHub App 连接现有私有仓库，只授予该仓库所需权限 |
| 部署 URL、動作確認の方法 | 使用本机私有的评审说明；本目录不含 URL、密码或邀请码 |

[官方条件](https://zenn.dev/hackathons/google-cloud-japan-ai-hackathon-vol5)允许私有仓库及需认证的部署，但要给评审提供不用社交登录或收邮件的账号和样例。正式提交后，默认分支与可用部署保留至12月1日；后续开发用其他分支。

## 录制与评审依据

- [demo-script-ja.md](demo-script-ja.md)：约3分钟的镜头、字幕和日语讲解，可按实际结果调整。
- [recording-checklist-zh.md](recording-checklist-zh.md)：直接开录的操作要点。
- [evidence-and-judging-ja.md](evidence-and-judging-ja.md)：文化厅统计、UNESCO政策背景、三项评分对应及验证边界。

项目主张是成人进入文学世界，与记得自己的角色相互影响，最后形成世界、人物和玩家三层结局。官方资料支持问题背景与文化学习方向；它们不证明本项目已经提升读书量、共情或学习成绩。当前实际收录一本书，不宣传其他作品已经可玩。

## 提交前最后核对

1. 赛事注册状态、成员条件、GitHub App连接均在本人赛事后台核对；材料完成不等于正式提交完成。
2. 视频为本人的实际操作，角色回复、事件和结局没有伪造；不同存档与省略等待需标明。
3. 公开说明、图片、视频和 YouTube描述均不含部署地址、邀请码、密码、个人云项目ID或真实用户资料。
4. 评审用部署URL、密码、主邀请码和备用邀请码只放在私有的「動作確認の方法」，不贴到公开说明。
5. 架构图和日语说明使用当前实现：Gemini负责人物语音和文字回复，Claude负责叙事等处理；不复制旧Firestore、ADK或Veo方案。
6. 填入真正上传成功的视频URL，保存并检查最终提交确认；不要把草稿保存或文件选择当成已提交。

架构图经两个角色核对并进行了视觉检查。最新代码仍保留已观察到的缺答与模板结局风险；200局和剩余CI按用户决定跳过。本次仅补提交材料，没有改变线上程序或移除密码。

## 重新生成架构图

使用具备 Pillow 的 Python 环境，运行 `build_visuals.py --font <日文字体文件>`。PNG和SVG由相同坐标、文字和连线生成，图只展示主要调用路径；网关也会调用Claude做安全和候选生成。
