"""预录句的生成（B-6）：用人物在 Live 里的同一个声音照读，三遍取一、自动检查，出声音清单 `voices.json`。

- `spec`：源文件 `services/backend/voice/<book>.json` + 世界模型 → 要生成的录音清单。
- `audio`：PCM 的分析（长度、截断）、裁静音、限峰值、编码（ffmpeg）。
- `checks`：自动检查和挑选（backend-design 3.6）。
- `models`：照读（Live）和补转写的真实现、假实现。
- `cli`：`zoujin-voice` 脚本（先打印预计花费，带 `--confirm` 才调用）。
"""
