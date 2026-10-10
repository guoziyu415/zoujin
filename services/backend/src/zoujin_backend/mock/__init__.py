"""B-1 mock 服务：同一个源上的 api-contract REST 和 WebSocket，按剧本回放写好的会话（给前端离线开发和 CI）。

不 import 数据库和叙事者的代码；状态只在内存里，重启就清空。剧本在 `fixtures/sessions/`，REST 的固定数据在
`fixtures/mock/rest/`，写法见那两个目录的 README。
"""
