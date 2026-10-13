# Mosaic · 本地视频社区

**v0.2.3 可运行功能版**。默认只允许本机访问。

## 已实现

- MP4/WebM流式上传、512MiB限额、SHA256去重、随机文件名、上传取消和残留回收
- 注册登录、scrypt密码哈希、会话过期撤销、作者页、本人编辑、隐藏和恢复作品
- 持久FFmpeg队列、重启恢复、失败重试、封面、不放大的480/720上限HLS、hls.js浏览器播放
- 转码总预算、作者排队/运行取消、直接子进程终止回收、完成前产物访问保护；原视频保留，取消后可明确重试
- 自产HLS片段字节/EXTINF实测峰值与平均码率，master/API持久记录、菜单明确未知旧码率，极短VOD边界标注
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
node --test tests/media_control_ui.cjs
```

48项Python测试：实际低清/竖屏/宽屏/方形/奇数尺寸/SAR/旋转媒体解码、旧队列兼容、账户/社区，11项取消/发布边界与13项实测码率边界（含60组独立精确窗口对拍、真实13秒4段短尾FFmpeg、Windows junction、变化检测/取消、拒绝坏清单后同worker重试）。平台权限测试明确skip。5项Node控制/响应代次/实际取消handler测试与16清晰度/码率断言。测试默认临时APP_DATA_DIR，不加载用户数据库。Linux CI用apt系统FFmpeg独立验证imageio生成的HLS（MEDIA_VERIFY_FFMPEG仅覆盖测试decoder）；bundled7.0.2短TS崩溃根因仍未定位。最新完整SHA与同SHA CI见本地维护报告。

## 已知边界

- 上传检查容器头；后台FFmpeg真实解码决定转码是否成功。不是同步ffprobe完整校验。
- 单进程本机队列；每次抢占任务后共用monotonic总预算，封面与两档不各自重置时限。默认300秒，服务端`MEDIA_JOB_TIMEOUT_SECONDS=1..3600`；排队时间不计。作者可取消，运行中先显示cancelling，直接FFmpeg结束/回收后为cancelled；完成/失败拒绝无意义取消，active任务拒绝重试。正常关闭中断并重新排队，取消重启仍取消；不是跨进程队列或进程树沙箱。数据库锁、文件IO、进程终止等待可超过媒体预算，不保证硬墙钟SLA。
- 每次attempt用独立暂存目录；成功后jobID资源目录与completed数据库指针发布，未完成/取消资源不提供。旧completed无指针仍兼容旧目录。失败/取消正常清理本attempt暂存，不删原视频或旧成功目录；进程崩溃/数据库发布失败可能留下不可访问目录，尚无GC/fsync断电保证。日志临时落盘、最多读取256KiB，但不是日志磁盘配额。
- 转码限制854×480/1280×720且不放大、偶数对齐、保留SAR；低清两档可能相同，尚未去重。完整媒体探测仍未完成。
- 新任务BANDWIDTH按RFC8216的连续片段窗口（0.5..1.5倍TARGETDURATION）计算最大bytes×8/EXTINF，AVERAGE-BANDWIDTH按总字节/总时长，精确有理数计算并向上取整，包含TS封装字节而非纯视频编码率/网络吞吐。总VOD短于最小窗口时采用最大单段rate并明确标极短片段；自产≤0.5秒清单TARGETDURATION:0仅在暂存修为1。1MiB/4096片段、只接受自产本地未加密VOD TS、安全文件名/普通文件/祖先非链接与观察元数据复验；失败不发布。仍不是完整probe、媒体真实性验证或恶意并发文件写者沙箱。
- master/API/菜单记录实际尺寸和新码率来源；旧任务无来源标记或元数据时明确“码率未实测”，不自动重转或修改旧产物。码率测量共用现有任务期限/取消；阻塞IO与检查后变化仍不保证硬实时或文件系统原子快照。
- 举报由作品所有者审阅，尚无独立平台管理员审核；同分区推荐不是学习式个性化推荐。
- 数据和媒体保存在本机；对象存储、CDN、分布式转码和公网部署仍待建设。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。

使用体验修正：观看位置续播、播放速度、HLS失败回退、手机行内播放与首页加载更多已接入。详细边界见docs/PROGRESS.md。
