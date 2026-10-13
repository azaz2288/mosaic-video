# 开发记录

## 2026-10-14 v0.2.3 HLS实测码率

- 首新测试缺media_bandwidth模块；实现精确Fraction连续目标窗口peak/整VOD average并ceil，SQLite/master/API持久化来源。旧历史1M/2M不再给新任务；UI旧来源/非法数值标未知，新菜单显示bps，極短VOD单段fallback明确标注。真实FFmpeg0.5秒输出target0，严格仅修自产staging为1，旧媒体不重写。
- 新13Python方法包含60组seeded独立枚举oracle、真实13秒FFmpeg四段与1秒短尾、小hot尾不能单段替标准窗口、精确小数/短片、结构/URI/限额、缺空/非普通文件、祖先symlink/真实Windows junction、观察后segment/playlist变化与计算期取消/deadline、坏测量失败不发布/原视频保留/同worker retry。旧取消/发布mock改生成有效合成playlist而非绕过measurement；真实6source两档重新解码，size/EXTINF独立核对API/master和重启metadata。最终48方法与同SHA平台结果见根本日报告；原35保留。
- Node5实际控制handler与16码率/legacy/非法数值断言通过。初变化fixture第8callback发生在stat之前，改第17点在统计窗口阶段，不将正常首次观察变化当漏洞。目录只比较身份/type，避免把兄弟文件创建误当路径替换。旧API列迁移不变。
- 独立临时8901原创8秒320x180/360x640，后者两档270x480/360x640实测226916/460788bps；IAB实际720HLS readyState4/duration8/360x640，390x844长标签横溢出533>375，CSS菜单限宽后body=client375/select343.2。早期点击未更新，只读CDP确认handler已绑定后正常点击成功，无事件修复或bug解决虚报。真实手机/用户8766未验未改。computer-use推动像素/移动验证，planning-with-files保存断点。
- 只测TS封装rate，不是完整probe/视频质量/网络吞吐/恶意媒体隔离；仍有重复低清档、check后竞态/阻塞IO、崩溃orphan/无fsync/硬限额、平台管理和公网待完。完整SHA/同SHA Windows/Linux CI与18项目最终核对在外部维护报告，避免纯证据文档再提交。

## 2026-10-11 v0.2.2 总预算/作者取消与产物保护

- 首5新方法在旧实现3fail/2missing-module errors，证实取消缺接口、active重试可替换行、partial资源会返回200。新增11方法最终35Python全通过28.997s；含真实sleep子进程cancel/timeout回收、跨调用共用deadline、结束后复验、关闭requeue、取消重启保持、最终编码后取消禁止发布、IO/超时通用错误脱敏、active retry/账户/Origin、日志读取限额和配置拒绝、旧成功目录保留/独占新产物、rename后SQLite事务回滚不服务orphan/同worker重试。持久DB不可用时的自动恢复仍不承诺。
- media_process.py在monotonic deadline内轮询直接FFmpeg，取消terminate/必要kill/wait。单任务默认300s、服务端1..3600，不把排队计入。attempt staging→唯一jobID目录→conditional completed/artifact指针；asset拒绝非completed与暂存，legacy空artifact兼容。无进程树隔离/硬资源沙箱、跨DB/FS原子断电/GC保证，崩溃或提交故障可留不可访问orphan。
- 页面作者取消/取消中/总预算、active禁重试、终态可显式重试。processing响应验证videoID+watch代次，旧响应不更新；5Node tests和原清晰度10assertions通过。actual cancel handler不在finally覆写cancelling禁用/导航后不重开旧响应；compileall/JS语法/diff/root5通过，既有FastAPI httpx弃用提示保留。
- 独立8897原创4秒320×180合成演示：queued取消→cancelled、原视频readyState4/duration4、重试后queued/disabled、390×844内容375px；新artifact目录HLS readyState4/duration4/320×180、console error/warn空；截图在本地maintenance/reports。演示worker暂停以确定排队UI，不冒称浏览器取消真实长FFmpeg（实际进程取消由Python边界验收）。不访问8766用户服务/私有视频/付费API。
- 完整probe/重复档去重/实测码率/公网部署仍未完成；当前源码发布完整SHA、同SHA Windows/Linux CI与18巡检证据保存在根每日报告，不用父提交绿灯冒充。

## 2026-10-07 v0.2.1 不放大转码阶段

- 第三2d3ded4 CI37507404789 bundledLinuxFFmpeg7.0.2仍在读取TS crash，不能宣称mpegts选择已修复。新增独立Linux系统FFmpeg验证输出（apt安装/明确MEDIA_VERIFY_FFMPEG，仅测试decoder替换；app/source生成仍imageio7），仍检查实际像素/两维/SAR/master，stderr失败可诊断。本地Windows默认bundleddecoder；新CI必须完成，崩溃历史保持公开。

- 第二2f4fa7a CI37507054068 Linux decode-to-RGB仍SIGSEGV，因此不能认定nullmuxer单独致因。第三验证明确已知MPEG-TS demuxer、取消输出segment无必要的noautorotate，保持真实像素/尺寸/SAR断言；不跳过Linux/重刷旧失败。具体内部库故障未定位，需新CI证明fixture decode路径兼容。

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
