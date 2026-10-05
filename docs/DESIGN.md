# 架构设计 · v0.2

main.py管理视频与互动；accounts.py提供账户和会话；community.py实现关注、历史、合集、通知与作品审阅。transcode.py在lifespan启动单个本机工作线程，SQLite事务抢占任务；媒体资源校验hidden状态和资源路径。FFmpeg由imageio-ffmpeg提供，hls.js处理浏览器MSE播放。

## 模块和边界

FastAPI + SQLite + 无构建原生Web UI。数据库外部调用不放入长写事务；默认Host/Origin校验、CSP和输入转义。

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；单任务转码超时5分钟，长视频可能失败；480/720会放大低分辨率视频。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。
