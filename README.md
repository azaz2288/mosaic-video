# Mosaic · 本地视频社区

参考视频社区的浏览与互动方式：真实视频上传、分类搜索、播放、评论、弹幕、点赞和收藏。首版为单用户本地工作台。

**状态：v0.1 可运行基础版，按路线图持续开发。默认只允许本机访问。**

## 已实现

- 限额流式上传 MP4/WebM，检查容器头并随机化存储名称
- 视频列表、搜索与分类；原生视频播放与HTTP Range
- 评论、带时间戳的弹幕、点赞与收藏持久化
- 播放页、弹幕显示开关与收藏筛选
- 清晰空状态，不填充虚构内容和播放统计

## 运行

需要 Python 3.12。Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8766
```

浏览器打开 http://127.0.0.1:8766 。其他系统用 `.venv/bin/python`；已安装依赖可直接运行 `run.cmd`。配置 `APP_DATA_DIR` 可改变数据目录。

## 数据

data/app.db 和 data/media/，用户视频、评论与收藏仅存本地。上传失败清除临时文件。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

CI在Linux和Windows运行相同测试。实际执行证据见 [进度](docs/PROGRESS.md)。

## 已知边界

- 仅绑定回环地址，尚无账户、生产权限或公网部署保障
- 没有FFmpeg转码；MP4/WebM容器校验不保证浏览器支持内部编码
- 单文件最高512MiB；评论与弹幕以本地用户身份保存
- 没有CDN、推荐算法、内容审核或版权内容；不复制B站素材和商标

## 设计与后续

- [架构设计](docs/DESIGN.md)
- [按顺序开发的里程碑](docs/ROADMAP.md)

MIT License。用户导入内容不随源码发布。
