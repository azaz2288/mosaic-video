# Mosaic · 本地视频社区

**v0.2.1 可运行功能版**。默认只允许本机访问。

## 已实现

- MP4/WebM流式上传、512MiB限额、SHA256去重、随机文件名、上传取消和残留回收
- 注册登录、scrypt密码哈希、会话过期撤销、作者页、本人编辑、隐藏和恢复作品
- 持久FFmpeg队列、重启恢复、失败重试、封面、不放大的480/720上限HLS、hls.js浏览器播放
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
node tests/media_profiles_ui.cjs
```

24项Python测试，包含实际低清/竖屏/宽屏/方形/奇数尺寸/SAR/旋转视频→封面→两档HLS→实际像素/尺寸校验，以及旧队列迁移、账户隔离与社区回归。Node验证清晰度标签与旧任务回退。测试启动默认临时APP_DATA_DIR，不加载现有用户数据库。Linux CI用apt系统FFmpeg独立验证imageio生成的HLS（MEDIA_VERIFY_FFMPEG仅测试decoder覆盖），避免bundled7.0.2读取短TS时的崩溃；Windows默认bundleddecoder。崩溃内部原因未定位，不保证此binary的任意媒体解码。最新同SHA发布证据见本地维护报告。

## 已知边界

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；每个FFmpeg调用超时5分钟，长视频可能失败，尚无任务取消。转码分别限制854×480/1280×720并不超过自动旋转后的解码帧；yuv420p向下对齐偶数，SAR保留显示比例。480/720是上限，不是输出承诺；低清两档可能相同，尚未去重。
- master与播放菜单记录实际编码尺寸；已完成旧任务未记录尺寸时明确标注，重试后可生成新元数据。BANDWIDTH仍为旧估计值，未测量峰值；输出日志尺寸解析不是完整媒体探测。旧转码文件不会自动重建。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。

使用体验修正：观看位置续播、播放速度、HLS失败回退、手机行内播放与首页加载更多已接入。详细边界见docs/PROGRESS.md。
