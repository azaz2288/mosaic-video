# Mosaic · 本地视频社区

**v0.2 可运行功能版**。默认只允许本机访问。

## 已实现

- MP4/WebM流式上传、512MiB限额、SHA256去重、随机文件名、上传取消和残留回收
- 注册登录、scrypt密码哈希、会话过期撤销、作者页、本人编辑、隐藏和恢复作品
- 持久FFmpeg队列、重启恢复、失败重试、封面、480p/720p HLS、hls.js浏览器播放
- 账户独立点赞收藏、关注、历史、合集、分页评论、弹幕节流、消息和作品举报记录
- FTS5标题/简介搜索，短词回退检索，分区筛选与带原因的同分区推荐

## 运行

Python 3.12，Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8766
```

打开 http://127.0.0.1:8766 。已有依赖时可用 `run.cmd`。其他系统使用 `.venv/bin/python`。`APP_DATA_DIR`覆盖数据目录。

## 数据与备份

数据位于data/，已排除Git；不要提交数据库、导入内容、磁盘清单或密钥。详细启动、备份和部署边界见 [运行说明](docs/OPERATIONS.md)。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

15项全部通过，包含真实生成视频→封面→两档HLS、跨用户编辑/收藏隔离、去重、历史合集和举报。浏览器HLS readyState=4，8.03秒媒体可解码。 Linux/Windows CI使用同一提交验证。

## 已知边界

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；单任务转码超时5分钟，长视频可能失败；480/720会放大低分辨率视频。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。
