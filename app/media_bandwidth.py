"""Measure only our bounded, local, unencrypted MPEG-TS VOD output.

RFC 8216 segment windows use 0.5..1.5 target durations, inclusive.
For a VOD shorter than the minimum window, report maximum individual rate
with an explicit fallback marker. This is not a network/codec media probe.
"""
from fractions import Fraction
import math, os, re, stat
from .media_process import check_deadline

MAX_PLAYLIST_BYTES = 1024 * 1024
MAX_SEGMENTS = 4096
SOURCE = 'measured-segment-windows-v1'


def fingerprint(path, directory=False):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) & 0x400 or
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise RuntimeError('HLS本地文件类型不受支持')
    identity = (info.st_dev, info.st_ino, info.st_mode)
    return identity if directory else identity + (info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def measure_playlist(path, deadline, check):
    def checkpoint():check_deadline(deadline, check)
    checkpoint()
    # Reject existing links/reparse points throughout the generated path.
    parents = [(parent, fingerprint(parent, True)) for parent in path.parents]
    initial = fingerprint(path)
    if initial[3] > MAX_PLAYLIST_BYTES:raise RuntimeError('HLS清单超过读取限额')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != initial[:2]:raise RuntimeError('HLS清单已变化')
        data = stream.read(MAX_PLAYLIST_BYTES + 1)
    checkpoint()
    if len(data) > MAX_PLAYLIST_BYTES or fingerprint(path) != initial:
        raise RuntimeError('HLS清单已变化或超过读取限额')
    try:rows = data.decode('ascii').splitlines()
    except UnicodeError as error:raise RuntimeError('HLS清单编码不受支持') from error
    if not rows or rows[0] != '#EXTM3U' or rows[-1] != '#EXT-X-ENDLIST':
        raise RuntimeError('HLS必须为完整VOD清单')
    headers = {};segments = [];pending = None;seen = set()
    for row in rows[1:-1]:
        checkpoint()
        if not row or len(row)>1024:raise RuntimeError('HLS清单行无效')
        if row.startswith('#EXTINF:'):
            if pending is not None or not re.fullmatch(r'#EXTINF:([0-9]{1,5}(?:\.[0-9]{1,6})?),',row):
                raise RuntimeError('HLS片段时长无效')
            pending = Fraction(row[8:-1])
            if pending<=0:raise RuntimeError('HLS片段时长无效')
        elif row.startswith('#'):
            key, separator, value = row.partition(':')
            if (pending is not None or segments or not separator or key in headers or
                    key not in {'#EXT-X-VERSION','#EXT-X-TARGETDURATION',
                                '#EXT-X-MEDIA-SEQUENCE','#EXT-X-PLAYLIST-TYPE'}):
                raise RuntimeError('HLS清单特性不受支持')
            headers[key]=value
        else:
            if pending is None or not re.fullmatch(r'segment[0-9]{5,}\.ts',row) or row in seen:
                raise RuntimeError('HLS片段路径无效')
            if len(segments)>=MAX_SEGMENTS:raise RuntimeError('HLS片段数超过限额')
            segment=path.parent/row;info=fingerprint(segment)
            if info[3]<=0:raise RuntimeError('HLS片段为空')
            segments.append((segment,pending,info));seen.add(row);pending=None
    raw_target=headers.get('#EXT-X-TARGETDURATION','')
    if (pending is not None or not segments or
            headers.get('#EXT-X-VERSION')!='3' or headers.get('#EXT-X-MEDIA-SEQUENCE')!='0' or
            headers.get('#EXT-X-PLAYLIST-TYPE')!='VOD' or
            not re.fullmatch(r'0|[1-9][0-9]{0,4}',raw_target)):
        raise RuntimeError('HLS清单结构无效')
    target=int(raw_target)
    if target>86400 or any(duration>target+Fraction(1,2) for _,duration,_ in segments):
        raise RuntimeError('HLS目标时长无效')
    # FFmpeg rounds the TARGETDURATION of <=0.5-second clips to zero.
    # Repair only our staging playlist, not old published artifacts.
    repair = target==0
    if repair:target=1
    low=Fraction(target,2);high=Fraction(3*target,2)
    peak=Fraction(0);total_duration=sum((s[1] for s in segments),Fraction(0))
    total_bytes=sum(s[2][3] for s in segments)
    for start in range(len(segments)):
        duration=Fraction(0);size=0
        for _,length,info in segments[start:]:
            checkpoint();duration+=length;size+=info[3]
            if duration>high:break
            if duration>=low:peak=max(peak,Fraction(8*size,1)/duration)
    window='target-duration'
    if not peak:
        if total_duration>=low:raise RuntimeError('HLS无法确定码率窗口')
        peak=max(Fraction(8*info[3],1)/duration for _,duration,info in segments)
        window='short-vod-single-segment'
    for segment,_,info in segments:
        checkpoint()
        if fingerprint(segment)!=info:raise RuntimeError('HLS片段已变化')
    for parent,info in parents:
        checkpoint()
        if fingerprint(parent,True)!=info:raise RuntimeError('HLS目录已变化')
    if fingerprint(path)!=initial:raise RuntimeError('HLS清单已变化')
    checkpoint()
    if repair:
        path.write_bytes(data.replace(b'#EXT-X-TARGETDURATION:0',b'#EXT-X-TARGETDURATION:1',1))
    checkpoint()
    return {'bandwidth':math.ceil(peak),
            'average_bandwidth':math.ceil(Fraction(8*total_bytes,1)/total_duration),
            'bandwidth_source':SOURCE,'bandwidth_window':window,
            'segment_count':len(segments),'duration_seconds':str(total_duration)}
