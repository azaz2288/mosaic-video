# 开发记录

## 2026-10-07 v0.2.1 不放大转码阶段

- 首提交49e05be CI37506634203真实Linux failure：6case在HLS转码成功后测试decode-to-null命令SIGSEGV（bundledLinuxFFmpeg7.0.2）；Windows测试/JS全成功但matrix取消，不标跨平台通过。测试改显式RGB rawvideo真实一帧，并检查字节数w×h×3，保留dims/SAR assertions；fail-fast关闭以保留完整两平台诊断。新提交需同SHA终态验证，不重刷旧run。

- 旧代码固定480/720高度且master硬编码尺寸。新增320×180验收旧代码缺variants失败；实现decoded-frame双维上限、偶数对齐、保留SAR，真实output stream尺寸用于master和持久API/UI。SQLite additive列迁移与显式INSERT兼容旧任务，旧媒体不自动重建。
- 24Python方法（8新增），真实6source subcases：竖屏、宽屏、方形、奇数尺寸、SAR=2、90°rotation，分别转两档并重新解码检查尺寸与显示比例；原低清case追加两档320×180/master校验。旧schema重复启动/metadata持久化/queued/legacy、parser不误取input尺寸及畸形fail-closed验证。
- Fixture首次5case失败为FFmpeg拒`.5`时长，改`0.5`；旧metadata rotate未写显示矩阵，改display_rotation后rotation通过，不当源码漏洞。Node UI边界、compile、JS syntax与根维护工具5tests通过；FastAPI现有httpx弃用警告仍在。
- 独立8893合成8秒视频浏览器：低清720档实际320×180、竖屏480档270×480，readyState4/duration8，清晰度标签准确、console errors=[]。截图存本地维护目录；未浏览8766现有服务/用户视频。demo生成与队列等待合计低清1.187s、竖屏1.062s，单机短片观察非长视频吞吐/SLA。
- 测试module-level bootstrap默认临时APP_DATA_DIR；demo用新temp，Enter停止服务后正常清理。完整SHA/同SHA CI终态存根maintenance报告，不用历史绿灯代替。
- 本次不完成完整probe、取消/总timeout、峰值bandwidth测量、重复档去重、公网部署。480/720是上限，两档低清可能同尺寸；旧媒体无自动升级。继续第一未完路线，非整个项目完工。

## v0.1 验证

- 上传、容器检查、随机文件名、Range播放、搜索、分类、评论、弹幕与个人收藏已实现。
- 修复通用互动路由遮蔽评论/弹幕路由，回归覆盖实际POST。
- 独立venv的9项测试全部通过；Python编译、前端JS语法通过。
- Chromium动态生成真实WebM，验证上传、解码播放、评论；桌面与390px移动截图检查，无脚本异常/横向溢出。
- 单用户本地首版；账户、转码、CDN等仍在路线图。

- 初版GitHub公开发布完成，Windows/Linux同提交CI成功；完整SHA与CI链接保存在本地维护报告。所有用户数据目录与环境配置均排除在Git之外。

## 2026-10-06 v0.2 功能扩展

- MP4/WebM流式上传、512MiB限额、SHA256去重、随机文件名、上传取消和残留回收
- 注册登录、scrypt密码哈希、会话过期撤销、作者页、本人编辑、隐藏和恢复作品
- 持久FFmpeg队列、重启恢复、失败重试、封面、480p/720p HLS、hls.js浏览器播放
- 账户独立点赞收藏、关注、历史、合集、分页评论、弹幕节流、消息和作品举报记录
- FTS5标题/简介搜索，短词回退检索，分区筛选与带原因的同分区推荐

15项全部通过，包含真实生成视频→封面→两档HLS、跨用户编辑/收藏隔离、去重、历史合集和举报。浏览器HLS readyState=4，8.03秒媒体可解码。

使用原创合成示例完成浏览器交互；未读取个人文件、未操作真实磁盘清理、未调用付费API。保留路线图中实际未完成项。

## 实际使用审查

修复每次打开视频将历史位置重置为0：新增按当前账户读取位置、暂停/返回保存、结束重置与加载元数据后续播。码率切换保留位置和播放状态，致命HLS错误回退原视频；返回页销毁HLS资源。补播放速度、playsinline和手机控件适配、首页超过40作品的加载更多入口。16项回归通过，新增历史隔离/隐藏访问/NaN与无穷位置拒绝。浏览器原视频及HLS加载和控件检查通过；真实iOS设备尚未验证。
