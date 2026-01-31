# SailZen Overview

SailZen是帮助我处理日常事务的核心工具，主要包括

- sail_server：一个运行在云服务器上的python server，后端接入PostgreSQL，用于日常信息的数据持久化，可以随时随地通过手机-电脑等接口查看-更新
- packages/site：一个通用的前端页面，build后会被sail_server托管，作为云服务器的前端操作页面
- packages/vscode_plugin: 基于Dendron的vscode插件，当前与sail_server/site相对独立，用于管理电脑上长期的笔记和日记，但是长期会联动sail_server/site实现更多好用的效果

长期来看，SailZen的目标是

- 帮助管理我日常生活中一切需要持久化记录的事务，包括个人账单，身体健康，project代办等
- 帮助管理日常生活的笔记（基于Dendron功能），尝试和使用最新的AI协助功能，测试对比AI工具，成为开发AI私人助理的试验田
- 帮助创作，包括
    - 网络小说和更多内容的存储，引用，阅读，链接，分析世界观
    - 帮助管理日常的创作进度（世界观设定完善，剧情大纲，写作任务管理，AI协助等）

