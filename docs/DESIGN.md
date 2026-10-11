# 架构设计 · v0.2.2

main.py管理视频与互动；accounts.py提供账户和会话；community.py实现关注、历史、合集、通知与作品审阅。transcode.py在lifespan启动单个本机工作线程，SQLite事务抢占任务；媒体资源校验hidden状态和资源路径。FFmpeg由imageio-ffmpeg提供，hls.js处理浏览器MSE播放。

## 模块和边界

FastAPI + SQLite + 无构建原生Web UI。数据库外部调用不放入长写事务；默认Host/Origin校验、CSP和输入转义。

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；media_process.py在抢占后以monotonic总deadline控制封面与两档，默认300秒（服务端整数1..3600），排队不计。50ms轮询取消/stop/deadline，直接进程terminate→wait1s→kill→wait2s，结束后再验取消/预算；不是进程树沙箱或硬墙钟SLA，DB锁/IO可超时。media_profiles.py仍不放大、偶数对齐并保留SAR。
- 从FFmpeg output stream读取实际编码尺寸，不能使用input stream或档位名字代替；无法确认则失败。成功两档写master RESOLUTION与SQLite variants_json，processing API公开variants，UI标签用实际尺寸。迁移添加列并使用显式INSERT字段，不丢旧任务。旧已完成任务无元数据时保留清单、明确未知尺寸；不自动重转旧数据。
- 两档低清可能重复，BANDWIDTH仍为未测量的历史估计；日志parser只提供输出尺寸，不是完整探测/恶意媒体隔离。FFMPEG_PATH覆盖须提供兼容滤镜与英文stream日志的版本；不支持时失败。只有imageio bundled Windows/Linux版本随CI验证。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

## 取消与产物发布

作者cancel在BEGIN IMMEDIATE内从queued→cancelled，running→cancelling，重复请求幂等；completed/failed返回409。运行者检查自己的jobID状态，终态UPDATE也要求同ID running/cancelling，active retry返回409。重启running→queued、cancelling→cancelled；正常lifespan退出stop/join直接子进程，未完成任务重新排队。这是单应用进程语义，不能另起多worker或运行中再次create_app重置队列。

attempt输出在processed/video/.work-*，正常异常自动回收；成功先在写事务中再验running/stop/deadline，把完整目录rename为唯一jobID，然后持久completed/variants/artifact_id。asset只读completed，artifact_id为空兼容旧目录；任何带点路径组件拒绝，不能浏览暂存。目录和DB不是跨存储原子事务：rename成功后commit失败/崩溃可留不可访问orphan，无fsync断电/GC保证。原输入与旧成功目录不删除；重试期间旧HLS URL也不服务，原视频仍可用。

stderr临时文件spool，成功只读≤256KiB，异常通用提示不返回本机路径/原始日志。spool不是硬磁盘/CPU/RSS限额。页面同videoID+watch代次复验processing响应，取消中轮询，返回或同片重入丢弃旧响应；不声称其他社区请求竞态已全部解决。
