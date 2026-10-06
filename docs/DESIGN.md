# 架构设计 · v0.2.1

main.py管理视频与互动；accounts.py提供账户和会话；community.py实现关注、历史、合集、通知与作品审阅。transcode.py在lifespan启动单个本机工作线程，SQLite事务抢占任务；媒体资源校验hidden状态和资源路径。FFmpeg由imageio-ffmpeg提供，hls.js处理浏览器MSE播放。

## 模块和边界

FastAPI + SQLite + 无构建原生Web UI。数据库外部调用不放入长写事务；默认Host/Origin校验、CSP和输入转义。

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；每个FFmpeg调用超时5分钟，长视频可能失败，取消未实现。media_profiles.py在实际解码（含自动旋转）帧上限制854×480/1280×720且两维不放大、偶数向下对齐；封面限制480×480，保留SAR显示比例。
- 从FFmpeg output stream读取实际编码尺寸，不能使用input stream或档位名字代替；无法确认则失败。成功两档写master RESOLUTION与SQLite variants_json，processing API公开variants，UI标签用实际尺寸。迁移添加列并使用显式INSERT字段，不丢旧任务。旧已完成任务无元数据时保留清单、明确未知尺寸；不自动重转旧数据。
- 两档低清可能重复，BANDWIDTH仍为未测量的历史估计；日志parser只提供输出尺寸，不是完整探测/恶意媒体隔离。FFMPEG_PATH覆盖须提供兼容滤镜与英文stream日志的版本；不支持时失败。只有imageio bundled Windows/Linux版本随CI验证。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。
